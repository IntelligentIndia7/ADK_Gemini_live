"""
Text client for a deployed Agent Engine voice agent.

Usage:
  python agent_engine/test_text.py
  python agent_engine/test_text.py --interactive
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import numpy as np
import vertexai
from dotenv import load_dotenv
from google.adk.agents.live_request_queue import LiveRequest
from google.adk.events import Event
from google.genai import types

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "voice_agent" / ".env", override=True)

PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")


def resource_name() -> str:
    if os.environ.get("AGENT_ENGINE_RESOURCE_NAME"):
        return os.environ["AGENT_ENGINE_RESOURCE_NAME"]
    return (Path(__file__).parent / "agent_resource_name.txt").read_text().strip()


def live_request_text(text: str) -> dict:
    return LiveRequest(
        content=types.Content(parts=[types.Part.from_text(text=text)])
    ).model_dump(mode="json", exclude_none=True)


async def chat(client: vertexai.Client, interactive: bool) -> None:
    queries = ["Hello, who are you?", "Tell me a one-sentence fun fact about space."]
    if interactive:
        queries = []

    async with client.aio.live.agent_engines.connect(
        agent_engine=resource_name(),
        config={"class_method": "bidi_stream_query"},
    ) as connection:
        user_id = "test-user"
        first = True

        while True:
            if interactive:
                text = input("You: ").strip()
                if text.lower() in {"exit", "quit"}:
                    break
            elif queries:
                text = queries.pop(0)
                print(f"\nYou: {text}")
            else:
                break

            if first:
                await connection.send(
                    {"user_id": user_id, "live_request": live_request_text(text)}
                )
                first = False
            else:
                await connection.send(live_request_text(text))

            audio_chunks: list[np.ndarray] = []
            print("Agent: ", end="", flush=True)

            while True:
                raw = await connection.receive()
                event_data = raw.get("bidiStreamOutput", raw)

                if isinstance(event_data, dict) and event_data.get("output") == "end of turn":
                    print()
                    break

                if not isinstance(event_data, dict):
                    continue

                actions = event_data.get("actions") or {}
                actions.pop("requested_tool_confirmations", None)

                try:
                    event = Event.model_validate(event_data)
                except Exception:
                    continue

                part = event.content and event.content.parts and event.content.parts[0]
                if not part:
                    if audio_chunks:
                        break
                    continue

                if part.inline_data and part.inline_data.data:
                    audio_chunks.append(
                        np.frombuffer(part.inline_data.data, dtype=np.int16)
                    )
                elif part.text:
                    print(part.text, end="", flush=True)

            if audio_chunks:
                duration = sum(len(c) for c in audio_chunks) / 24000
                print(f"[audio response ~{duration:.1f}s at 24kHz]")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--interactive", action="store_true")
    args = parser.parse_args()

    vertexai.init(project=PROJECT_ID, location=LOCATION)
    client = vertexai.Client(project=PROJECT_ID, location=LOCATION)
    print(f"Agent: {resource_name()}")
    asyncio.run(chat(client, args.interactive))


if __name__ == "__main__":
    main()
