# Task Dub-4 Brief: Mixagem de Áudio com Ducking no Renderizador FFmpeg

## Objetivos
Expandir o `VideoRenderer` em `src/editor/renderer.py` para suportar mixagem de áudio secundário (dublagem) com atenuação automática (ducking a 15% / -16dB) do áudio original no FFmpeg.

## Arquivos a modificar
1. `src/editor/renderer.py`:
   - Atualizar `build_filter_complex`:
     - Adicionar parâmetro `has_dubbing: bool = False, ducking_volume: float = 0.15`.
     - Se `has_dubbing` for `True`, adicionar filtros de áudio:
       `[0:a]volume={ducking_volume}[bg_audio];[1:a]volume=1.0[fg_audio];[bg_audio][fg_audio]amix=inputs=2:duration=first:dropout_transition=2[aout]`
   - Atualizar `build_ffmpeg_render_command`:
     - Parâmetros: `(input_video, output_video, filter_complex, dubbing_audio: Optional[Path | str] = None, ffmpeg_bin: str = "ffmpeg")`.
     - Se `dubbing_audio` for fornecido:
       - Adiciona `-i {dubbing_audio}` após `-i {input_video}`.
       - Adiciona `-filter_complex {filter_complex} -map "[vout]" -map "[aout]"` (ou se não houver dublagem, `-vf {filter_complex}`).
   - Atualizar `VideoRenderer.render_clip`:
     - Adicionar parâmetro `dubbing_audio: Optional[Union[Path, str]] = None, ducking_volume: float = 0.15`.
     - Validar que se `dubbing_audio` for passado, o arquivo deve existir.
     - Montar o comando e executar via FFmpeg gerando o vídeo final 9:16 com o áudio original atenuado e a voz dublada proeminente.
2. `tests/test_renderer.py`:
   - Adicionar testes verificando:
     - `build_filter_complex` gerando os blocos `volume` e `amix` quando `has_dubbing=True`.
     - `build_ffmpeg_render_command` incluindo segundo `-i` e mapeamentos corretos `-map "[vout]" -map "[aout]"`.
     - `render_clip` com mock de FFmpeg aceitando `dubbing_audio` e tratando arquivo de áudio inexistente.

## Critérios de Aceite
- Executar `pytest tests/test_renderer.py -v` com 100% de sucesso.
- Executar toda a suíte `pytest tests/` garantindo zero regressões.
- Fazer commit: `feat: audio ducking and dual-audio mixing in video renderer`.
