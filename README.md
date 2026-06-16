# ADK Gemini Live Voice

Minimal voice agent with **local mic**, **local browser UI**, and **Vertex AI Agent Engine** deployment.

## Layout

```
voice_agent/
  agent.py              # Agent definition (deployed to Agent Engine)
  .env.example          # Copy to .env and fill in

clients/
  local_mic_client.py           # Mic → Runner.run_live() (local)
  agent_engine_mic_client.py    # Mic → deployed Agent Engine
  mic_common.py / audio_gate.py # Shared run config + echo guard

local_server/           # Browser UI → local Runner.run_live()

agent_engine/
  deploy.py             # Deploy to Agent Engine
  cleanup.py            # Delete deployment
  test_text.py          # Text-only smoke test (no mic)
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[agent-engine]"

# macOS mic support
brew install portaudio

cp voice_agent/.env.example voice_agent/.env   # edit project, bucket, region
gcloud auth application-default login
```

## Local voice (no deploy)

**Python mic client** (same idea as `adk web` voice mode):

```bash
python clients/local_mic_client.py
```

**Browser UI:**

```bash
uvicorn local_server.main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000

## Agent Engine

**Deploy:**

```bash
python agent_engine/deploy.py
```

Resource name is saved to `agent_engine/agent_resource_name.txt` (gitignored).

**Mic client:**

```bash
python clients/agent_engine_mic_client.py
```

**Text smoke test:**

```bash
python agent_engine/test_text.py --interactive
```

**Teardown:**

```bash
python agent_engine/cleanup.py
```

## Audio format

| Direction | Format |
|-----------|--------|
| Mic in    | 16-bit PCM mono 16 kHz |
| Speaker out | 16-bit PCM mono 24 kHz |

Headphones recommended. Mic clients mute input while the agent speaks to reduce speaker echo.

## Agent Engine checklist

1. `agent_server_mode: EXPERIMENTAL` in deploy (required for `bidi_stream_query`)
2. Native-audio Live model on Vertex (`gemini-live-2.5-flash-native-audio`)
3. `GOOGLE_GENAI_USE_VERTEXAI=TRUE` — no API key on Agent Engine
4. Caller needs `roles/aiplatform.user` (includes `reasoningEngines.query`)
5. First `bidi_stream_query` message must include `user_id` and `run_config`

Reference: [google/adk-samples bidi-demo](https://github.com/google/adk-samples/tree/main/python/agents/bidi-demo)
