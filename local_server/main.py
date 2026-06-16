"""
Local voice server — same pattern as adk web / bidi-demo.

Run from repo root:
  uvicorn local_server.main:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
import json
import logging
import warnings
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from google.adk.agents.live_request_queue import LiveRequestQueue
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

load_dotenv(Path(__file__).resolve().parents[1] / "voice_agent" / ".env", override=True)

from voice_agent.agent import root_agent  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

APP_NAME = "voice-local"
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="ADK Voice Local Server")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

session_service = InMemorySessionService()
runner = Runner(app_name=APP_NAME, agent=root_agent, session_service=session_service)


def build_run_config() -> RunConfig:
    model_name = root_agent.model
    is_native_audio = "native-audio" in model_name.lower()
    if is_native_audio:
        return RunConfig(
            streaming_mode=StreamingMode.BIDI,
            response_modalities=["AUDIO"],
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
        )
    return RunConfig(
        streaming_mode=StreamingMode.BIDI,
        response_modalities=["TEXT"],
    )


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.websocket("/ws/{user_id}/{session_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str, session_id: str) -> None:
    await websocket.accept()
    run_config = build_run_config()

    session = await session_service.get_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    if not session:
        await session_service.create_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )

    live_request_queue = LiveRequestQueue()

    async def upstream() -> None:
        while True:
            message = await websocket.receive()
            if "bytes" in message:
                blob = types.Blob(
                    mime_type="audio/pcm;rate=16000",
                    data=message["bytes"],
                )
                live_request_queue.send_realtime(blob)
            elif "text" in message:
                payload = json.loads(message["text"])
                if payload.get("type") == "text":
                    live_request_queue.send_content(
                        types.Content(parts=[types.Part(text=payload["text"])])
                    )

    async def downstream() -> None:
        async for event in runner.run_live(
            user_id=user_id,
            session_id=session_id,
            live_request_queue=live_request_queue,
            run_config=run_config,
        ):
            await websocket.send_text(
                event.model_dump_json(exclude_none=True, by_alias=True)
            )

    try:
        await asyncio.gather(upstream(), downstream())
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    finally:
        live_request_queue.close()
