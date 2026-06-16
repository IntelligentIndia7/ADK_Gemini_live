"""
Talk to voice_agent via microphone — same behaviour as `adk web` voice mode.

Uses Runner.run_live() with bidirectional PCM audio (16 kHz in, 24 kHz out).

Setup (macOS):
  brew install portaudio
  pip install pyaudio

Run from repo root:
  python clients/local_mic_client.py
"""

from __future__ import annotations

import asyncio
import sys
import uuid
import warnings
from pathlib import Path

import pyaudio
from dotenv import load_dotenv
from google.adk.agents.live_request_queue import LiveRequestQueue
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / "voice_agent" / ".env", override=True)

from clients.mic_common import build_voice_run_config, make_speaker_gate  # noqa: E402
from voice_agent.agent import root_agent  # noqa: E402

warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

APP_NAME = "voice-assistant"
INPUT_RATE = 16000
OUTPUT_RATE = 24000
CHANNELS = 1
FORMAT = pyaudio.paInt16
CHUNK = 1600  # 100 ms at 16 kHz


def print_transcription(event) -> None:
    inp = getattr(event, "input_transcription", None)
    if inp and inp.text:
        print(f"\nYou: {inp.text}")
    out = getattr(event, "output_transcription", None)
    if out and out.text:
        print(f"Agent: {out.text}")


async def run_session() -> None:
    user_id = "local-user"
    session_id = str(uuid.uuid4())

    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )

    runner = Runner(
        app_name=APP_NAME,
        agent=root_agent,
        session_service=session_service,
    )
    run_config = build_voice_run_config()
    live_request_queue = LiveRequestQueue()
    gate = make_speaker_gate()

    pa = pyaudio.PyAudio()
    mic = pa.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=INPUT_RATE,
        input=True,
        frames_per_buffer=CHUNK,
    )
    speaker = pa.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=OUTPUT_RATE,
        output=True,
        frames_per_buffer=CHUNK,
    )

    print(
        "Voice session started. Echo guard on (mic muted while agent speaks).\n"
        "Headphones recommended. Press Ctrl+C to stop.\n"
    )

    async def send_mic() -> None:
        loop = asyncio.get_running_loop()
        while True:
            pcm = await loop.run_in_executor(
                None,
                lambda: mic.read(CHUNK, exception_on_overflow=False),
            )
            pcm = gate.filter_pcm(pcm)
            blob = types.Blob(mime_type="audio/pcm;rate=16000", data=pcm)
            live_request_queue.send_realtime(blob)

    async def receive_agent() -> None:
        async for event in runner.run_live(
            user_id=user_id,
            session_id=session_id,
            live_request_queue=live_request_queue,
            run_config=run_config,
        ):
            print_transcription(event)
            if event.turn_complete:
                gate.notify_turn_complete()
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        print(f"Agent: {part.text}")
                    if part.inline_data and part.inline_data.data:
                        gate.notify_agent_audio(
                            len(part.inline_data.data), output_rate=OUTPUT_RATE
                        )
                        speaker.write(part.inline_data.data)

    send_task = asyncio.create_task(send_mic())
    recv_task = asyncio.create_task(receive_agent())
    try:
        await asyncio.gather(send_task, recv_task)
    finally:
        live_request_queue.close()
        mic.stop_stream()
        mic.close()
        speaker.stop_stream()
        speaker.close()
        pa.terminate()


def main() -> None:
    try:
        asyncio.run(run_session())
    except KeyboardInterrupt:
        print("\nStopped.")
    except ImportError:
        print("Install pyaudio: pip install pyaudio  (macOS: brew install portaudio first)")
        sys.exit(1)


if __name__ == "__main__":
    main()
