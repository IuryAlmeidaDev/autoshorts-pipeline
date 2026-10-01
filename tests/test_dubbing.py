"""Testes para o módulo de dublagem e síntese de voz neural (Edge-TTS)."""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from src.dubbing.voice_synthesizer import (
    DEFAULT_FEMALE_VOICE,
    DEFAULT_MALE_VOICE,
    VoiceSynthesizer,
    VoiceSynthesisError,
)
from src.editor.subtitles import WordTimestamp


class MockAsyncStream:
    """Mock assíncrono para communicate.stream()."""

    def __init__(self, chunks):
        self.chunks = chunks

    def __aiter__(self):
        self._iter = iter(self.chunks)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class TestVoiceSynthesizerInit:
    """Testes de inicialização e seleção de vozes."""

    def test_default_init(self, tmp_path):
        synth = VoiceSynthesizer(temp_dir=tmp_path)
        assert synth.male_voice == DEFAULT_MALE_VOICE
        assert synth.female_voice == DEFAULT_FEMALE_VOICE
        assert synth.temp_dir == tmp_path

    def test_custom_voices(self, tmp_path):
        synth = VoiceSynthesizer(
            temp_dir=tmp_path,
            male_voice="pt-BR-CustomMale",
            female_voice="pt-BR-CustomFemale",
        )
        assert synth.male_voice == "pt-BR-CustomMale"
        assert synth.female_voice == "pt-BR-CustomFemale"

    def test_get_voice_for_gender(self, tmp_path):
        synth = VoiceSynthesizer(temp_dir=tmp_path)
        assert synth.get_voice_for_gender("female") == DEFAULT_FEMALE_VOICE
        assert synth.get_voice_for_gender("FEMALE") == DEFAULT_FEMALE_VOICE
        assert synth.get_voice_for_gender("Female") == DEFAULT_FEMALE_VOICE
        assert synth.get_voice_for_gender("male") == DEFAULT_MALE_VOICE
        assert synth.get_voice_for_gender("MALE") == DEFAULT_MALE_VOICE
        assert synth.get_voice_for_gender("unknown") == DEFAULT_MALE_VOICE
        assert synth.get_voice_for_gender("") == DEFAULT_MALE_VOICE


class TestVoiceSynthesizerValidation:
    """Testes de validação de parâmetros."""

    def test_empty_text_raises_error(self, tmp_path):
        synth = VoiceSynthesizer(temp_dir=tmp_path)
        with pytest.raises((VoiceSynthesisError, ValueError)):
            asyncio.run(synth.synthesize_async(""))

    def test_whitespace_text_raises_error(self, tmp_path):
        synth = VoiceSynthesizer(temp_dir=tmp_path)
        with pytest.raises((VoiceSynthesisError, ValueError)):
            asyncio.run(synth.synthesize_async("   \n\t  "))

    def test_non_string_text_raises_error(self, tmp_path):
        synth = VoiceSynthesizer(temp_dir=tmp_path)
        with pytest.raises((VoiceSynthesisError, TypeError, ValueError)):
            asyncio.run(synth.synthesize_async(None))  # type: ignore


class TestVoiceSynthesizerSynthesis:
    """Testes de síntese de áudio e extração de timestamps."""

    def test_synthesize_async_success(self, tmp_path):
        synth = VoiceSynthesizer(temp_dir=tmp_path)

        fake_chunks = [
            {"type": "audio", "data": b"ID3_HEADER_CHUNK_"},
            {
                "type": "WordBoundary",
                "offset": 10_000_000,  # 1.0s
                "duration": 5_000_000,  # 0.5s -> end 1.5s
                "text": "Olá",
            },
            {"type": "audio", "data": b"AUDIO_DATA_PAYLOAD"},
            {
                "type": "WordBoundary",
                "offset": 15_000_000,  # 1.5s
                "duration": 4_000_000,  # 0.4s -> end 1.9s
                "text": "mundo",
            },
        ]

        mock_communicate = MagicMock()
        mock_communicate.stream.return_value = MockAsyncStream(fake_chunks)

        with patch("edge_tts.Communicate", return_value=mock_communicate) as mock_cls:
            audio_path, words = asyncio.run(
                synth.synthesize_async(
                    text="Olá mundo",
                    voice_gender="female",
                    output_filename="test_output.mp3",
                )
            )

            # Verifica se o edge_tts foi chamado com a voz feminina e boundary
            mock_cls.assert_called_once_with(
                "Olá mundo",
                DEFAULT_FEMALE_VOICE,
                boundary="WordBoundary",
            )

            # Verifica o arquivo gerado
            assert audio_path.exists()
            assert audio_path == tmp_path / "test_output.mp3"
            assert audio_path.read_bytes() == b"ID3_HEADER_CHUNK_AUDIO_DATA_PAYLOAD"

            # Verifica os timestamps
            assert len(words) == 2
            assert words[0] == WordTimestamp(word="Olá", start=1.0, end=1.5)
            assert words[1] == WordTimestamp(word="mundo", start=1.5, end=1.9)

    def test_synthesize_async_default_filename(self, tmp_path):
        synth = VoiceSynthesizer(temp_dir=tmp_path)

        fake_chunks = [
            {"type": "audio", "data": b"AUDIO_DATA"},
            {
                "type": "WordBoundary",
                "offset": 0,
                "duration": 10_000_000,
                "text": "Teste",
            },
        ]

        mock_communicate = MagicMock()
        mock_communicate.stream.return_value = MockAsyncStream(fake_chunks)

        with patch("edge_tts.Communicate", return_value=mock_communicate):
            audio_path, words = asyncio.run(synth.synthesize_async("Teste", voice_gender="male"))
            assert audio_path.exists()
            assert audio_path.parent == tmp_path
            assert audio_path.suffix == ".mp3"
            assert len(words) == 1
            assert words[0].word == "Teste"
            assert words[0].start == 0.0
            assert words[0].end == 1.0

    def test_synthesize_async_absolute_output_filename(self, tmp_path):
        synth = VoiceSynthesizer(temp_dir=tmp_path)
        custom_out = tmp_path / "subdir" / "my_custom.mp3"

        fake_chunks = [
            {"type": "audio", "data": b"AUDIO_DATA"},
        ]
        mock_communicate = MagicMock()
        mock_communicate.stream.return_value = MockAsyncStream(fake_chunks)

        with patch("edge_tts.Communicate", return_value=mock_communicate):
            audio_path, words = asyncio.run(
                synth.synthesize_async(
                    "Teste",
                    output_filename=str(custom_out),
                )
            )
            assert audio_path == custom_out
            assert audio_path.exists()
            assert audio_path.read_bytes() == b"AUDIO_DATA"

    def test_synthesize_async_stream_error_raises_voice_synthesis_error(self, tmp_path):
        synth = VoiceSynthesizer(temp_dir=tmp_path)

        class ErrorStream:
            def __aiter__(self):
                return self

            async def __anext__(self):
                raise ConnectionResetError("Falha na conexão com edge-tts")

        mock_communicate = MagicMock()
        mock_communicate.stream.return_value = ErrorStream()

        with patch("edge_tts.Communicate", return_value=mock_communicate):
            with pytest.raises(VoiceSynthesisError) as excinfo:
                asyncio.run(synth.synthesize_async("Texto com falha de conexão"))
            assert "Falha" in str(excinfo.value) or "Erro" in str(excinfo.value)

    def test_synthesize_async_no_audio_received_raises_error(self, tmp_path):
        synth = VoiceSynthesizer(temp_dir=tmp_path)

        # Stream vazio sem chunks de áudio
        fake_chunks = [
            {"type": "WordBoundary", "offset": 0, "duration": 1000, "text": "Vazio"}
        ]
        mock_communicate = MagicMock()
        mock_communicate.stream.return_value = MockAsyncStream(fake_chunks)

        with patch("edge_tts.Communicate", return_value=mock_communicate):
            with pytest.raises(VoiceSynthesisError) as excinfo:
                asyncio.run(synth.synthesize_async("Texto sem áudio"))
            assert "Nenhum dado de áudio" in str(excinfo.value) or "vazio" in str(excinfo.value).lower()

    def test_sync_synthesize_wrapper(self, tmp_path):
        synth = VoiceSynthesizer(temp_dir=tmp_path)

        fake_chunks = [
            {"type": "audio", "data": b"SYNC_AUDIO"},
            {"type": "WordBoundary", "offset": 0, "duration": 5_000_000, "text": "Sincrono"},
        ]
        mock_communicate = MagicMock()
        mock_communicate.stream.return_value = MockAsyncStream(fake_chunks)

        with patch("edge_tts.Communicate", return_value=mock_communicate):
            audio_path, words = synth.synthesize("Sincrono", voice_gender="male")
            assert audio_path.exists()
            assert audio_path.read_bytes() == b"SYNC_AUDIO"
            assert len(words) == 1
            assert words[0].word == "Sincrono"
