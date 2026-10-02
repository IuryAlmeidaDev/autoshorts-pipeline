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

    def generate_suspense_bgm(
        self,
        duration_sec: float = 60.0,
        bpm: float = 120.0,
        framerate: int = 44100,
    ) -> Path:
        """Sintetiza uma trilha sonora atmosférica de suspense e foco com pulso rítmico a 120 BPM."""
        import array
        file_path = self.output_dir / f"suspense_bgm_{int(duration_sec)}s_{int(bpm)}bpm.wav"
        if file_path.exists() and file_path.stat().st_size > 10000:
            return file_path

        n_frames = int(duration_sec * framerate)
        audio = [0.0] * n_frames
        beat_interval = 60.0 / bpm

        # 1. Pad atmosférico cinematográfico contínuo (drones em 110Hz A2 e 164.8Hz E3)
        for i in range(n_frames):
            t = i / framerate
            mod = 0.5 + 0.5 * math.sin(2 * math.pi * 0.25 * t)
            drone = 0.10 * math.sin(2 * math.pi * 110.0 * t) + 0.07 * math.sin(2 * math.pi * 164.81 * t)
            drone += 0.03 * math.sin(2 * math.pi * 220.0 * t + 0.5)
            audio[i] += drone * (0.65 + 0.35 * mod)

        # 2. Pulso de sub-grave rítmico (efeito batimento cardíaco / tensão contínua)
        beat_frames = int(beat_interval * framerate)
        n_beats = int(duration_sec / beat_interval)
        pulse_len = int(0.18 * framerate)

        for b in range(n_beats):
            start_idx = int(b * beat_frames)
            for j in range(pulse_len):
                if start_idx + j < n_frames:
                    t_p = j / framerate
                    env = math.exp(-j / (pulse_len * 0.3))
                    freq = 65.0 - (20.0 * (j / pulse_len))
                    kick = 0.30 * env * math.sin(2 * math.pi * freq * t_p)
                    audio[start_idx + j] += kick

        # 3. Tique-taque sutil em semicolcheias (clockwork suspense)
        half_interval = beat_interval / 2.0
        n_half = int(duration_sec / half_interval)
        click_len = int(0.02 * framerate)

        for h in range(n_half):
            idx = int(h * half_interval * framerate)
            for k in range(click_len):
                if idx + k < n_frames:
                    decay = math.exp(-k / (click_len * 0.2))
                    tick = 0.05 * decay * math.sin(2 * math.pi * 3200.0 * k / framerate)
                    audio[idx + k] += tick

        raw_samples = array.array("h")
        for val in audio:
            sample = int(max(min(val * 0.65, 1.0), -1.0) * 32767)
            raw_samples.append(sample)
            raw_samples.append(sample)

        with wave.open(str(file_path), "w") as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(framerate)
            wav.writeframes(raw_samples.tobytes())

        return file_path

