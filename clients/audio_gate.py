"""Client-side mic gating for loudspeaker use (reduces echo and noise triggers)."""

from __future__ import annotations

import struct
import time


def pcm_rms(pcm: bytes) -> float:
    """Root-mean-square level for 16-bit mono PCM."""
    count = len(pcm) // 2
    if count == 0:
        return 0.0
    samples = struct.unpack(f"<{count}h", pcm)
    mean_sq = sum(s * s for s in samples) / count
    return mean_sq**0.5


class SpeakerDuplexGate:
    """Drop mic audio while the agent plays and during a short echo tail."""

    def __init__(
        self,
        *,
        chunk_bytes: int,
        echo_cooldown_s: float = 0.5,
        energy_threshold: float = 400.0,
    ) -> None:
        self._silence = b"\x00" * chunk_bytes
        self._echo_cooldown_s = echo_cooldown_s
        self._energy_threshold = energy_threshold
        self._echo_until = 0.0

    def notify_agent_audio(self, nbytes: int, *, output_rate: int = 24000) -> None:
        duration = nbytes / (output_rate * 2)
        self._echo_until = max(
            self._echo_until,
            time.monotonic() + duration + self._echo_cooldown_s,
        )

    def notify_turn_complete(self) -> None:
        self._echo_until = max(
            self._echo_until,
            time.monotonic() + self._echo_cooldown_s,
        )

    def filter_pcm(self, pcm: bytes) -> bytes:
        if time.monotonic() < self._echo_until:
            return self._silence
        if pcm_rms(pcm) < self._energy_threshold:
            return self._silence
        return pcm
