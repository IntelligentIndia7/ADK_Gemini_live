"""Shared mic session settings for local and Agent Engine voice clients."""

from __future__ import annotations

import os

from google.adk.agents.run_config import RunConfig, StreamingMode
from google.genai import types

from clients.audio_gate import SpeakerDuplexGate

CHUNK_BYTES = 1600 * 2  # 100 ms @ 16 kHz, 16-bit mono


def build_voice_run_config() -> RunConfig:
    """Audio + transcription with conservative VAD for speaker use."""
    return RunConfig(
        streaming_mode=StreamingMode.BIDI,
        response_modalities=["AUDIO"],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(
                start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_LOW,
                end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_HIGH,
                prefix_padding_ms=300,
                silence_duration_ms=900,
            ),
            activity_handling=types.ActivityHandling.NO_INTERRUPTION,
        ),
    )


def make_speaker_gate() -> SpeakerDuplexGate:
    cooldown_ms = float(os.environ.get("MIC_ECHO_COOLDOWN_MS", "500"))
    threshold = float(os.environ.get("MIC_ENERGY_THRESHOLD", "400"))
    return SpeakerDuplexGate(
        chunk_bytes=CHUNK_BYTES,
        echo_cooldown_s=cooldown_ms / 1000.0,
        energy_threshold=threshold,
    )
