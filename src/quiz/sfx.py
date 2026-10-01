"""Gerador autônomo de efeitos sonoros sintetizados para vídeos de quiz."""

import math
from pathlib import Path
import struct
from typing import Optional, Union
import wave


class SoundEffectsGenerator:
    """Sintetiza efeitos sonoros para temporizador, revelação e transições."""

    def __init__(self, output_dir: Optional[Union[Path, str]] = None):
        self.output_dir = Path(output_dir or "storage/temp")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_countdown(self, duration_sec: int = 3, framerate: int = 44100) -> Path:
        """Gera áudio de contagem regressiva com cliques de relógio sincronizados a cada segundo."""
        file_path = self.output_dir / f"countdown_{duration_sec}s.wav"
        n_frames = framerate * duration_sec
        audio = [0.0] * n_frames

        # Ticks a cada segundo exato (0s, 1s, 2s...)
        for sec in range(duration_sec):
            start_idx = int(sec * framerate)
            tick_duration = 0.08
            tick_n = int(tick_duration * framerate)
            is_last = (sec == duration_sec - 1)
            freq = 1600.0 if is_last else 1200.0

            for i in range(tick_n):
                if start_idx + i < n_frames:
                    decay = math.exp(-i / (tick_n * 0.25))
                    val = 0.55 * decay * math.sin(2 * math.pi * freq * i / framerate)
                    audio[start_idx + i] += val

        with wave.open(str(file_path), "w") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(framerate)
            for val in audio:
                sample = int(max(min(val, 1.0), -1.0) * 32767)
                wav.writeframes(struct.pack("<h", sample))

        return file_path

    def generate_ding(self, duration_sec: float = 1.2, framerate: int = 44100) -> Path:
        """Gera sino alegre e cristalino de acerto com harmônicos ricos."""
        file_path = self.output_dir / "ding_correct.wav"
        total_frames = int(duration_sec * framerate)

        with wave.open(str(file_path), "w") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(framerate)
            for i in range(total_frames):
                t = i / framerate
                decay = math.exp(-t * 3.8)
                val = 0.45 * decay * (
                    0.60 * math.sin(2 * math.pi * 880.0 * t) +
                    0.30 * math.sin(2 * math.pi * 1760.0 * t) +
                    0.10 * math.sin(2 * math.pi * 2640.0 * t)
                )
                sample = int(max(min(val, 1.0), -1.0) * 32767)
                wav.writeframes(struct.pack("<h", sample))

        return file_path
