"""
Deploy voice_agent to Vertex AI Agent Engine (bidi streaming / Live API).

Usage:
  python agent_engine/deploy.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "voice_agent" / ".env", override=True)

sys.path.insert(0, str(ROOT))

import vertexai  # noqa: E402
from vertexai import types as vertexai_types  # noqa: E402
from vertexai.preview.reasoning_engines import AdkApp  # noqa: E402

from voice_agent.agent import agent  # noqa: E402

PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
STAGING_BUCKET = os.environ.get("STAGING_BUCKET") or os.environ.get(
    "GOOGLE_CLOUD_STAGING_BUCKET"
)
if not STAGING_BUCKET:
    raise SystemExit(
        "Set STAGING_BUCKET or GOOGLE_CLOUD_STAGING_BUCKET in voice_agent/.env"
    )

RESOURCE_FILE = Path(__file__).parent / "agent_resource_name.txt"


def main() -> None:
    vertexai.init(project=PROJECT_ID, location=LOCATION, staging_bucket=STAGING_BUCKET)
    client = vertexai.Client(project=PROJECT_ID, location=LOCATION)

    print(f"Project:  {PROJECT_ID}")
    print(f"Region:   {LOCATION}")
    print(f"Bucket:   {STAGING_BUCKET}")
    print(f"Model:    {agent.model}")

    def session_service_builder():
        from google.adk.sessions.in_memory_session_service import InMemorySessionService

        return InMemorySessionService()

    def memory_service_builder():
        from google.adk.memory.in_memory_memory_service import InMemoryMemoryService

        return InMemoryMemoryService()

    app = AdkApp(
        agent=agent,
        session_service_builder=session_service_builder,
        memory_service_builder=memory_service_builder,
    )

    print("\nDeploying to Agent Engine (EXPERIMENTAL mode for bidi streaming)...")
    print("This usually takes 3–8 minutes.\n")

    remote = client.agent_engines.create(
        agent=app,
        config={
            "display_name": "voice_assistant",
            "description": "Voice assistant with Gemini Live API bidi streaming",
            "staging_bucket": STAGING_BUCKET,
            "agent_server_mode": vertexai_types.AgentServerMode.EXPERIMENTAL,
            "env_vars": {
                "GOOGLE_GENAI_USE_VERTEXAI": "TRUE",
                # GOOGLE_CLOUD_PROJECT is reserved — set automatically by Agent Engine
                "GOOGLE_CLOUD_LOCATION": LOCATION,
                "VOICE_AGENT_MODEL": agent.model,
            },
            "requirements": [
                "google-cloud-aiplatform[agent_engines,adk]>=1.112",
                "google-adk",
                "google-genai",
                "cloudpickle",
                "pydantic",
            ],
        },
    )

    resource_name = remote.api_resource.name
    RESOURCE_FILE.write_text(resource_name)
    print(f"\nDeployed successfully!")
    print(f"Resource: {resource_name}")
    print(f"Saved:    {RESOURCE_FILE}")
    print("\nTest with:")
    print("  python clients/agent_engine_mic_client.py")


if __name__ == "__main__":
    main()
