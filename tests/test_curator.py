"""Testes unitários para o módulo de curadoria de transcrição e analisador de momentos virais."""

import json
from unittest.mock import MagicMock, patch
import pytest

from src.curator.transcript import (
    TranscriptSegment,
    TranscriptFetcher,
    TranscriptNotFoundError,
    format_transcript_with_timestamps,
)
from src.curator.analyzer import (
    ClipMetadata,
    CuratorAnalyzer,
    parse_llm_clip_response,
)


# ==========================================
# 1. Testes de Transcrição e Formatação
# ==========================================

def test_transcript_segment_dataclass():
    segment = TranscriptSegment(text="Olá mundo", start=12.5, duration=3.0)
    assert segment.text == "Olá mundo"
    assert segment.start == 12.5
    assert segment.duration == 3.0
    assert segment.end == 15.5


def test_format_transcript_with_timestamps_empty():
    assert format_transcript_with_timestamps([]) == ""
    assert format_transcript_with_timestamps(None) == ""


def test_format_transcript_with_timestamps_grouping():
    segments = [
        TranscriptSegment(text="Primeira frase.", start=0.0, duration=4.0),
        TranscriptSegment(text="Segunda frase.", start=5.0, duration=3.0),
        TranscriptSegment(text="Terceira frase.", start=16.0, duration=4.0),
        TranscriptSegment(text="Quarta frase.", start=35.0, duration=5.0),
    ]

    formatted = format_transcript_with_timestamps(segments, chunk_interval=15)
    
    # Deve conter blocos com timestamps formatados MM:SS
    assert "[00:00 - 00:15]" in formatted
    assert "Primeira frase. Segunda frase." in formatted
    assert "[00:15 - 00:30]" in formatted
    assert "Terceira frase." in formatted
    assert "[00:30 - 00:45]" in formatted
    assert "Quarta frase." in formatted


def test_format_transcript_with_timestamps_hour_format():
    segments = [
        TranscriptSegment(text="Momento épico após 1 hora.", start=3660.0, duration=10.0),
    ]
    formatted = format_transcript_with_timestamps(segments, chunk_interval=15)
    assert "[01:01:00 - 01:01:15]" in formatted
    assert "Momento épico após 1 hora." in formatted


def test_fetch_transcript_success_with_api_mock():
    fetcher = TranscriptFetcher()

    mock_raw_data = [
        {"text": "Sejam bem-vindos ao podcast.", "start": 1.2, "duration": 3.4},
        {"text": "Hoje o papo é sobre IA.", "start": 4.8, "duration": 2.5},
    ]

    with patch.object(fetcher, "_get_raw_transcript", return_value=mock_raw_data):
        segments = fetcher.fetch_transcript("vid_123", languages=["pt", "en"])

        assert len(segments) == 2
        assert segments[0].text == "Sejam bem-vindos ao podcast."
        assert segments[0].start == 1.2
        assert segments[0].duration == 3.4
        assert segments[1].text == "Hoje o papo é sobre IA."


def test_fetch_transcript_not_found_safe_return():
    fetcher = TranscriptFetcher()

    with patch.object(fetcher, "_get_raw_transcript", side_effect=Exception("TranscriptsDisabled")):
        # Por padrão retorna lista vazia de forma segura
        segments = fetcher.fetch_transcript("vid_without_subs", raise_on_error=False)
        assert segments == []


def test_fetch_transcript_not_found_raises_exception():
    fetcher = TranscriptFetcher()

    with patch.object(fetcher, "_get_raw_transcript", side_effect=Exception("NoTranscriptFound")):
        with pytest.raises(TranscriptNotFoundError):
            fetcher.fetch_transcript("vid_without_subs", raise_on_error=True)


def test_fetch_transcript_empty_or_invalid_id():
    fetcher = TranscriptFetcher()
    assert fetcher.fetch_transcript("") == []
    assert fetcher.fetch_transcript("   ") == []
    assert fetcher.fetch_transcript(None) == []


# ==========================================
# 2. Testes de Parsing de Resposta da LLM
# ==========================================

def test_parse_llm_clip_response_valid_json():
    json_text = json.dumps([
        {
            "start_time": 60.0,
            "end_time": 120.0,
            "hook_title": "O MAIOR SEGREDO REVELADO!",
            "description": "Veja como tudo começou do zero.",
            "hashtags": ["#podcast", "#viral", "#segredo"],
            "viral_score": 9.5,
        }
    ])

    clips = parse_llm_clip_response(json_text)
    assert len(clips) == 1
    clip = clips[0]
    assert clip.start_time == 60.0
    assert clip.end_time == 120.0
    assert clip.hook_title == "O MAIOR SEGREDO REVELADO!"
    assert clip.description == "Veja como tudo começou do zero."
    assert clip.hashtags == ["#podcast", "#viral", "#segredo"]
    assert clip.viral_score == 9.5


def test_parse_llm_clip_response_markdown_json_block():
    markdown_text = """Aqui estão os melhores cortes selecionados:
```json
[
  {
    "start_time": 15.0,
    "end_time": 75.0,
    "hook_title": "NÃO FAÇA ISSO ANTES DE VER ESTE VÍDEO!",
    "description": "Dica indispensável para criadores.",
    "hashtags": ["#shorts", "#dica"],
    "viral_score": 8.7
  }
]
```
Espero que goste dos resultados!"""

    clips = parse_llm_clip_response(markdown_text)
    assert len(clips) == 1
    assert clips[0].start_time == 15.0
    assert clips[0].end_time == 75.0
    assert clips[0].hook_title == "NÃO FAÇA ISSO ANTES DE VER ESTE VÍDEO!"


def test_parse_llm_clip_response_wrapped_dict_format():
    wrapped_json = json.dumps({
        "clips": [
            {
                "start_time": 30.0,
                "end_time": 90.0,
                "hook_title": "A VERDADE QUE NINGUÉM TE CONTA",
                "description": "Explicação completa.",
                "hashtags": ["#cortes"],
                "viral_score": 9.0,
            }
        ]
    })

    clips = parse_llm_clip_response(wrapped_json)
    assert len(clips) == 1
    assert clips[0].start_time == 30.0
    assert clips[0].end_time == 90.0


def test_parse_llm_clip_response_filters_invalid_times_and_durations():
    raw_data = json.dumps([
        # Caso 1: start >= end (inválido)
        {
            "start_time": 100.0,
            "end_time": 80.0,
            "hook_title": "Inválido 1",
            "viral_score": 5.0,
        },
        # Caso 2: duração menor que min_duration (45s)
        {
            "start_time": 10.0,
            "end_time": 30.0,  # 20s
            "hook_title": "Curto demais",
            "viral_score": 7.0,
        },
        # Caso 3: duração maior que max_duration (90s)
        {
            "start_time": 10.0,
            "end_time": 150.0,  # 140s
            "hook_title": "Longo demais",
            "viral_score": 6.0,
        },
        # Caso 4: Válido (duração 60s)
        {
            "start_time": 20.0,
            "end_time": 80.0,
            "hook_title": "CORTE PERFEITO",
            "viral_score": 9.2,
        },
    ])

    clips = parse_llm_clip_response(raw_data, min_duration=45, max_duration=90)
    assert len(clips) == 1
    assert clips[0].hook_title == "CORTE PERFEITO"


def test_parse_llm_clip_response_corrupted_or_empty():
    assert parse_llm_clip_response("") == []
    assert parse_llm_clip_response("   ") == []
    assert parse_llm_clip_response(None) == []
    assert parse_llm_clip_response("Texto qualquer sem JSON válido.") == []
    assert parse_llm_clip_response("{objeto_malformado:") == []


# ==========================================
# 3. Testes do Analisador CuratorAnalyzer
# ==========================================

def test_curator_analyzer_no_api_key_graceful_fallback():
    # Sem API key, deve retornar lista vazia sem quebrar a execução
    analyzer = CuratorAnalyzer(api_key="")
    clips = analyzer.analyze_transcript("[00:00 - 00:30] Conteúdo de teste.")
    assert clips == []


def test_curator_analyzer_empty_transcript():
    analyzer = CuratorAnalyzer(api_key="fake-test-key")
    assert analyzer.analyze_transcript("") == []
    assert analyzer.analyze_transcript("   ") == []
    assert analyzer.analyze_transcript(None) == []


def test_curator_analyzer_successful_generation():
    analyzer = CuratorAnalyzer(api_key="valid-test-key")

    mock_llm_response = MagicMock()
    mock_llm_response.text = json.dumps([
        {
            "start_time": 45.0,
            "end_time": 105.0,
            "hook_title": "O SEGREDO DO SUCESSO!",
            "description": "Momento em que o convidado conta a virada de chave.",
            "hashtags": ["#mindset", "#podcast", "#shorts"],
            "viral_score": 9.4,
        },
        {
            "start_time": 150.0,
            "end_time": 210.0,
            "hook_title": "ELE QUASE DESISTIU TUDO",
            "description": "História emocionante sobre superação.",
            "hashtags": ["#superacao", "#foco"],
            "viral_score": 8.8,
        },
    ])

    with patch.object(analyzer, "_call_gemini_api", return_value=mock_llm_response.text):
        transcript_sample = "[00:45 - 01:45] O segredo do sucesso foi nunca parar.\n[02:30 - 03:30] Eu quase desisti de tudo."
        clips = analyzer.analyze_transcript(transcript_sample, max_clips=3, min_duration=45, max_duration=90)

        assert len(clips) == 2
        assert clips[0].hook_title == "O SEGREDO DO SUCESSO!"
        assert clips[0].viral_score == 9.4
        assert clips[1].hook_title == "ELE QUASE DESISTIU TUDO"


def test_curator_analyzer_api_error_graceful_fallback():
    analyzer = CuratorAnalyzer(api_key="valid-test-key")

    with patch.object(analyzer, "_call_gemini_api", side_effect=Exception("API Connection Error")):
        # Em caso de erro de rede ou API, retorna lista vazia com log e sem exceção fatal
        clips = analyzer.analyze_transcript("[00:00 - 01:00] Teste com falha de rede.")
        assert clips == []


def test_curator_analyzer_respects_max_clips():
    analyzer = CuratorAnalyzer(api_key="valid-test-key")

    mock_json = json.dumps([
        {"start_time": 10.0, "end_time": 60.0, "hook_title": f"Corte {i}", "viral_score": 9.0}
        for i in range(5)
    ])

    with patch.object(analyzer, "_call_gemini_api", return_value=mock_json):
        clips = analyzer.analyze_transcript("[00:00 - 05:00] Transcrição longa...", max_clips=2, min_duration=45, max_duration=90)
        assert len(clips) == 2
