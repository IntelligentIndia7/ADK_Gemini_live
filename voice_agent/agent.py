"""Voice agent definition — deployed as-is to Agent Engine via AdkApp.

Keep only agent config here (model, instruction). No credentials or client code.
"""

import os

from google.adk.agents import Agent

root_agent = Agent(
    name="voice_assistant",
    model=os.getenv("VOICE_AGENT_MODEL", "gemini-live-2.5-flash-native-audio"),
    instruction=(
        "You are a friendly voice assistant. Keep replies concise and conversational. "
        "Respond naturally as if speaking aloud. "
        "ALWAYS respond in English. "
        "Never respond in Hindi or any other language. "
        "Keep responses concise and conversational."
    ),
)

agent = root_agent
