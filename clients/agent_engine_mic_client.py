"""
Voice client for a deployed Agent Engine agent.

Uses client.aio.live.agent_engines.connect() + bidi_stream_query.
This is the Agent Engine equivalent of local_mic_client.py.

Prerequisites:
  - python agent_engine/deploy.py   (once)
  - gcloud auth application-default login  OR service account key

Run from repo root:
  python clients/agent_engine_mic_client.py

Loudspeaker tip: mic is muted while the agent speaks (echo guard). Use
headphones for best results. Tune MIC_ENERGY_THRESHOLD / MIC_ECHO_COOLDOWN_MS
in voice_agent/.env if needed.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pyaudio
import vertexai
from dotenv import load_dotenv
from google.adk.agents.live_request_queue import LiveRequest
from google.adk.events import Event
from google.genai import types

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / "voice_agent" / ".env", override=True)

from clients.mic_common import build_voice_run_config, make_speaker_gate  # noqa: E402

PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

INPUT_RATE = 16000
OUTPUT_RATE = 24000
CHANNELS = 1
FORMAT = pyaudio.paInt16
CHUNK = 1600

RESOURCE_FILE = ROOT / "agent_engine" / "agent_resource_name.txt"


def agent_resource_name() -> str:
    if os.environ.get("AGENT_ENGINE_RESOURCE_NAME"):
        return os.environ["AGENT_ENGINE_RESOURCE_NAME"]
    if not RESOURCE_FILE.exists():
        raise FileNotFoundError(
            "Deploy first: python agent_engine/deploy.py\n"
            "Or set AGENT_ENGINE_RESOURCE_NAME in voice_agent/.env"
        )
    return RESOURCE_FILE.read_text().strip()


def live_request_blob(pcm: bytes) -> dict:
    return LiveRequest(
        blob=types.Blob(mime_type="audio/pcm;rate=16000", data=pcm)
    ).model_dump(mode="json", exclude_none=True)


def build_run_config() -> dict:
    return build_voice_run_config().model_dump(mode="json", exclude_none=True)


def print_event_transcription(event: Event) -> None:
    inp = event.input_transcription
    if inp and inp.text:
        print(f"\nYou: {inp.text}")
    out = event.output_transcription
    if out and out.text:
        print(f"Agent: {out.text}")


async def run_session() -> None:
    resource = agent_resource_name()
    vertexai.init(project=PROJECT_ID, location=LOCATION)
    client = vertexai.Client(project=PROJECT_ID, location=LOCATION)

    pa = pyaudio.PyAudio()
    mic = pa.open(
        format=FORMAT, channels=CHANNELS, rate=INPUT_RATE,
        input=True, frames_per_buffer=CHUNK,
    )
    speaker = pa.open(
        format=FORMAT, channels=CHANNELS, rate=OUTPUT_RATE,
        output=True, frames_per_buffer=CHUNK,
    )

    print(
        f"Agent Engine voice session\nResource: {resource}\n"
        "Echo guard on (mic muted while agent speaks). "
        "Headphones recommended.\nPress Ctrl+C to stop.\n"
    )

    stop = asyncio.Event()
    gate = make_speaker_gate()

    async with client.aio.live.agent_engines.connect(
        agent_engine=resource,
        config={"class_method": "bidi_stream_query"},
    ) as connection:
        user_id = "mic-user"
        first = True

        async def send_mic() -> None:
            nonlocal first
            loop = asyncio.get_running_loop()
            while not stop.is_set():
                pcm = await loop.run_in_executor(
                    None,
                    lambda: mic.read(CHUNK, exception_on_overflow=False),
                )
                pcm = gate.filter_pcm(pcm)
                req = live_request_blob(pcm)
                if first:
                    await connection.send({
                        "user_id": user_id,
                        "live_request": req,
                        "run_config": build_run_config(),
                    })
                    first = False
                else:
                    await connection.send(req)

        async def recv_agent() -> None:
            while not stop.is_set():
                raw = await connection.receive()
                event_data = raw.get("bidiStreamOutput", raw)
                if not isinstance(event_data, dict):
                    continue
                if event_data.get("output") == "end of turn":
                    gate.notify_turn_complete()
                    continue

                actions = event_data.get("actions") or {}
                actions.pop("requested_tool_confirmations", None)

                try:
                    event = Event.model_validate(event_data)
                except Exception:
                    continue

                print_event_transcription(event)
                if event.turn_complete:
                    gate.notify_turn_complete()

                part = event.content and event.content.parts and event.content.parts[0]
                if not part:
                    continue
                if part.inline_data and part.inline_data.data:
                    gate.notify_agent_audio(len(part.inline_data.data), output_rate=OUTPUT_RATE)
                    speaker.write(part.inline_data.data)
                elif part.text:
                    print(f"Agent: {part.text}")

        send_task = asyncio.create_task(send_mic())
        recv_task = asyncio.create_task(recv_agent())
        try:
            await asyncio.gather(send_task, recv_task)
        finally:
            stop.set()
            send_task.cancel()
            recv_task.cancel()

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
        print("pip install pyaudio google-cloud-aiplatform[agent_engines,adk]")
        sys.exit(1)


if __name__ == "__main__":
    main()
