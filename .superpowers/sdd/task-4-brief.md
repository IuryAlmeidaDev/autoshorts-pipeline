# Task 4 Brief: IA Curadora e Analisador de Transcrição

## Objetivos
Construir o motor de inteligência artificial que obtém a transcrição de um vídeo e utiliza um modelo de linguagem (Gemini) para identificar os momentos mais virais, com marcação de início/fim, gancho textual no topo, descrição e hashtags.

## Arquivos a criar
1. `src/curator/__init__.py`
2. `src/curator/transcript.py`
3. `src/curator/analyzer.py`
4. `tests/test_curator.py`

## Especificações Técnicas

### 1. `src/curator/transcript.py`
- Dataclass `TranscriptSegment`:
  - `text: str`
  - `start: float`
  - `duration: float`
- Classe `TranscriptFetcher`:
  - `fetch_transcript(video_id: str, languages: list[str] = ['pt', 'pt-BR', 'en']) -> list[TranscriptSegment]`
    - Usa `youtube_transcript_api.YouTubeTranscriptApi` para buscar a transcrição.
    - Se falhar ou não houver transcrição, lança `TranscriptNotFoundError` ou retorna lista vazia de forma segura.
  - `format_transcript_with_timestamps(segments: list[TranscriptSegment], chunk_interval: int = 15) -> str`:
    - Agrupa texto com marcações legíveis de tempo: `[01:15 - 01:30] Texto falado...`
    - Essencial para alimentar a LLM com contexto temporal preciso.

### 2. `src/curator/analyzer.py`
- Dataclass `ClipMetadata`:
  - `start_time: float`
  - `end_time: float`
  - `hook_title: str`
  - `description: str`
  - `hashtags: list[str]`
  - `viral_score: float`
- Função `parse_llm_clip_response(raw_text: str) -> list[ClipMetadata]`:
  - Faz parsing robusto de JSON (inclusive tratando blocos markdown ```json ... ```).
  - Valida se `start_time < end_time` e se a duração respeita os limites.
- Classe `CuratorAnalyzer`:
  - `__init__(self, api_key: str = "", model_name: str = "gemini-2.5-flash")`
  - Prompt estruturado solicitando momentos de alta retenção (polêmica, revelação, conselho, história engraçada ou emocionante) entre 45s e 90s.
  - `analyze_transcript(transcript_formatted: str, max_clips: int = 3, min_duration: int = 45, max_duration: int = 90) -> list[ClipMetadata]`:
    - Chama a API do Gemini com structured output/JSON mode.
    - Trata erros de rede, cota ou resposta vazia retornando lista vazia sem quebrar a aplicação.

## Testes (`tests/test_curator.py`)
- Testar `format_transcript_with_timestamps` com segmentos de teste.
- Testar `parse_llm_clip_response` com respostas JSON válidas, respostas com markdown, e com campos faltantes.
- Testar `TranscriptFetcher` com mock de `YouTubeTranscriptApi.get_transcript`.
- Testar `CuratorAnalyzer` com mock da chamada do Gemini.

## Critérios de Aceite
- Executar `pytest tests/test_curator.py -v` com 100% de sucesso.
- Executar toda a suíte `pytest tests/` garantindo zero regressões.
- Git commit: `feat: ai transcript curation and viral moment detector`.
