import asyncio
import json
import os

from fastapi import FastAPI, WebSocket, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.websockets import WebSocketState
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from dotenv import load_dotenv, dotenv_values
from sqlalchemy.orm import Session

from db.db import engine, get_db_session
from db.models.BaseModel import Base
from routes import chatting_routes, room_routes
from routes.chatting_routes import add_chat

load_dotenv()

app = FastAPI()

Base.metadata.create_all(bind=engine)

key = os.environ.get("OPENAI_API_KEY")
print("KEY", key)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

app.mount('/static', StaticFiles(directory='static'), name='static')

origins = [
    "http://localhost:5174"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chatting_routes.router)
app.include_router(room_routes.router)


@app.get("/")
async def get():
    with open(os.path.join(os.path.dirname(__file__), "templates", "test.html")) as fh:
        data = fh.read()
    return HTMLResponse(content=data, media_type="text/html")


@app.websocket('/infer')
async def websocket_endpoint(websocket: WebSocket, db: Session = Depends(get_db_session)):
    await websocket.accept()
    while True and websocket.client_state == WebSocketState.CONNECTED:
        if websocket.client_state != WebSocketState.CONNECTED:
            break

        data = await websocket.receive_text()

        print('data:', data)

        # parsing data (json text) to dict
        # data
        # msg = string
        # room_id = int
        data = json.loads(data)

        stream = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": data['msg']}],
            stream=True,
        )

        infer_text = ""

        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                current_content = chunk.choices[0].delta.content
                infer_text += current_content

                await websocket.send_text(current_content)

                await asyncio.sleep(0.01)

            else:
                await websocket.close()

        print('str:', infer_text)

        add_chat(room_id=data['room_id'], question=data['msg'], answer=infer_text, db=db)
