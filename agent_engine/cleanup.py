"""Delete the deployed Agent Engine instance."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import vertexai

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "voice_agent" / ".env", override=True)

PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
RESOURCE_FILE = Path(__file__).parent / "agent_resource_name.txt"


def main() -> None:
    resource_name = os.environ.get("AGENT_ENGINE_RESOURCE_NAME") or RESOURCE_FILE.read_text().strip()
    vertexai.init(project=PROJECT_ID, location=LOCATION)
    client = vertexai.Client(project=PROJECT_ID, location=LOCATION)
    client.agent_engines.delete(name=resource_name, force=True)
    print(f"Deleted: {resource_name}")
    if RESOURCE_FILE.exists():
        RESOURCE_FILE.unlink()


if __name__ == "__main__":
    main()
