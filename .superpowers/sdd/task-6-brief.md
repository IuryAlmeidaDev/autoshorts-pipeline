# Task 6 Brief: Legendas Dinâmicas e Reenquadramento Vertical (9:16)

## Objetivos
Construir o motor de edição que transforma um corte horizontal de podcast em um vídeo vertical de alto impacto visual (1080x1920, 9:16) com gancho textual no topo e legendas dinâmicas animadas estilo karaokê (Hormozi/CapCut).

## Arquivos a criar
1. `src/editor/subtitles.py`
2. `src/editor/renderer.py`
3. `tests/test_renderer.py`

## Especificações Técnicas

### 1. `src/editor/subtitles.py`
- Dataclass `WordTimestamp`:
  - `word: str`
  - `start: float`
  - `end: float`
- `generate_ass_subtitle(words: list[WordTimestamp], words_per_screen: int = 3, highlight_color: str = "&H0000FFFF") -> str`:
  - Gera arquivo de legenda `.ass` (Advanced SubStation Alpha).
  - Define estilo com fonte pesada (`Arial Black` / `Montserrat Black`), alinhamento inferior central (`Alignment=2`), tamanho 48-60, borda preta espessa (`Outline=4`), cor primária branca (`&H00FFFFFF`) e destaque em amarelo/verde (`&H0000FFFF` ou `&H0000FF00`).
  - Agrupa palavras em pequenas janelas (ex: 2 a 4 palavras) para leitura dinâmica rápida.
  - Gera tags de temporização ou eventos pontuais que destacam a palavra corrente.
- `extract_subtitles_with_whisper(audio_or_video_path: Path | str, model_size: str = "base") -> list[WordTimestamp]`:
  - Invoca `faster_whisper.WhisperModel(model_size, device="cpu", compute_type="int8")` com `word_timestamps=True`.
  - Converte as palavras e tempos retornados em lista de `WordTimestamp`.
  - Tratamento defensivo caso Whisper não esteja instalado ou em ambiente de teste sem modelos baixados.

### 2. `src/editor/renderer.py`
- Classe `VideoRenderer`:
  - `__init__(self, temp_dir: Path | str, output_dir: Path | str)`
  - `build_filter_complex(mode: str, subtitle_ass_path: Path | str = None, hook_text: str = None) -> str`:
    - Suporta 2 modos de enquadramento 9:16 (1080x1920):
      1. `smart_crop`: Recorta o vídeo 16:9 verticalmente (`crop=ih*9/16:ih:(iw-ow)/2:0,scale=1080:1920`).
      2. `blurred_background`: Fundo desfocado 1080x1920 (crop+scale+boxblur) com o vídeo 16:9 posicionado no centro.
    - Se `hook_text` for fornecido: adiciona overlay ou filtro `drawtext` no topo (Y=180-240) com fundo contrastante ou borda para o gancho viral.
    - Se `subtitle_ass_path` for fornecido: adiciona filtro `ass={subtitle_path}` ou `subtitles={subtitle_path}`.
  - `build_ffmpeg_render_command(input_video: Path | str, output_video: Path | str, filter_complex: str) -> list[str]`:
    - Argumentos otimizados: `-y -i {input_video} -vf {filter_complex} -c:v libx264 -preset fast -crf 22 -c:a aac -b:a 192k -ar 44100 {output_video}`.
  - `render_clip(input_video: Path | str, hook_text: str, words: list[WordTimestamp], output_name: str, mode: str = "smart_crop") -> Path`:
    - Salva o `.ass` temporário gerado por `generate_ass_subtitle`.
    - Executa o FFmpeg (via `subprocess.run`).
    - Valida a geração do MP4 final e retorna o caminho absoluto.

## Testes (`tests/test_renderer.py`)
- Testar `generate_ass_subtitle` com lista de palavras e verificar presença das seções `[Script Info]`, `[V4+ Styles]`, `[Events]`, estilos de cores e textos das palavras.
- Testar `build_filter_complex` para modos `smart_crop` e `blurred_background` com e sem gancho/legendas.
- Testar `build_ffmpeg_render_command` garantindo parâmetros corretos de codec e saída.
- Testar `VideoRenderer.render_clip` usando mock de subprocess do FFmpeg para validar o fluxo de ponta a ponta sem exigir execução real do binário do FFmpeg no ambiente de teste.

## Critérios de Aceite
- Executar `pytest tests/test_renderer.py -v` com 100% de aprovação.
- Executar toda a suíte `pytest tests/` garantindo zero regressões.
- Git commit: `feat: dynamic viral subtitles and 9:16 vertical video renderer`.
