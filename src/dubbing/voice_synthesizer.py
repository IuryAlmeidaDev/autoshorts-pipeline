"""Módulo de síntese de voz neural utilizando edge-tts com extração de timestamps palavra por palavra."""

import asyncio
import concurrent.futures
import logging
from pathlib import Path
from typing import Optional, Union
import uuid

import edge_tts

from src.config import settings
from src.editor.subtitles import WordTimestamp

logger = logging.getLogger(__name__)

DEFAULT_MALE_VOICE = "pt-BR-AntonioNeural"
DEFAULT_FEMALE_VOICE = "pt-BR-FranciscaNeural"


class VoiceSynthesisError(Exception):
    """Exceção levantada em falhas durante a síntese de voz neural."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class VoiceSynthesizer:
    """Sintetizador de voz neural com suporte a vozes masculinas/femininas e word timestamps."""

    def __init__(
        self,
        temp_dir: Optional[Union[Path, str]] = None,
        male_voice: str = DEFAULT_MALE_VOICE,
        female_voice: str = DEFAULT_FEMALE_VOICE,
    ):
        self.male_voice = male_voice
        self.female_voice = female_voice
        self.temp_dir = Path(temp_dir or settings.TEMP_DIR)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def get_voice_for_gender(self, gender: str) -> str:
        """Retorna o identificador de voz apropriado baseado no gênero solicitado."""
        if str(gender).strip().lower() == "female":
            return self.female_voice
        return self.male_voice

    async def synthesize_async(
        self,
        text: str,
        voice_gender: str = "male",
        output_filename: Optional[Union[Path, str]] = None,
    ) -> tuple[Path, list[WordTimestamp]]:
        """Sintetiza áudio assincronamente a partir de texto com edge-tts e extrai timestamps de palavras."""
        if not isinstance(text, str):
            raise VoiceSynthesisError("Texto para síntese deve ser uma string válida.")

        clean_text = text.strip()
        if not clean_text:
            raise VoiceSynthesisError("Texto para síntese não pode ser vazio.")

        voice = self.get_voice_for_gender(voice_gender)

        if output_filename:
            target = Path(output_filename)
            dest_path = target if target.is_absolute() else self.temp_dir / target
        else:
            dest_path = self.temp_dir / f"tts_{uuid.uuid4().hex[:8]}.mp3"

        dest_path.parent.mkdir(parents=True, exist_ok=True)

        words: list[WordTimestamp] = []
        audio_received = False

        try:
            communicate = edge_tts.Communicate(clean_text, voice, boundary="WordBoundary")
            with open(dest_path, "wb") as f:
                async for chunk in communicate.stream():
                    chunk_type = chunk.get("type")
                    if chunk_type == "audio":
                        data = chunk.get("data", b"")
                        if data:
                            f.write(data)
                            audio_received = True
                    elif chunk_type == "WordBoundary":
                        offset = chunk.get("offset", 0)
                        duration = chunk.get("duration", 0)
                        word = chunk.get("text", "")
                        start = offset / 10_000_000.0
                        end = (offset + duration) / 10_000_000.0
                        words.append(WordTimestamp(word=word, start=start, end=end))
        except Exception as e:
            if dest_path.exists():
                dest_path.unlink(missing_ok=True)
            raise VoiceSynthesisError(f"Erro na síntese de voz: {e}") from e

        if not audio_received or not dest_path.exists() or dest_path.stat().st_size == 0:
            if dest_path.exists():
                dest_path.unlink(missing_ok=True)
            raise VoiceSynthesisError("Nenhum dado de áudio foi recebido durante a síntese.")

        return dest_path, words

    def synthesize(
        self,
        text: str,
        voice_gender: str = "male",
        output_filename: Optional[Union[Path, str]] = None,
    ) -> tuple[Path, list[WordTimestamp]]:
        """Invoca a síntese de forma síncrona para permitir integração simples com pipelines síncronos."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(
                    asyncio.run,
                    self.synthesize_async(text, voice_gender, output_filename),
                ).result()
        else:
            return asyncio.run(
                self.synthesize_async(text, voice_gender, output_filename)
            )
