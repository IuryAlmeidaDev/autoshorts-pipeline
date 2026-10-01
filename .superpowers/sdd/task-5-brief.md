# Task 5 Brief: Download Cirúrgico de Segmentos

## Objetivos
Implementar o módulo responsável por baixar exclusivamente o intervalo de tempo identificado pela IA (ex: dos 14m30s aos 15m45s) utilizando `yt-dlp`, sem a necessidade de baixar o podcast completo de 2 a 3 horas.

## Arquivos a criar
1. `src/editor/__init__.py`
2. `src/editor/downloader.py`
3. `tests/test_downloader.py`

## Especificações Técnicas (`src/editor/downloader.py`)

1. Função `format_time_sec_to_hms(seconds: float) -> str`:
   - Converte segundos decimais em formato de tempo: `00:01:24.500`.

2. Função `build_ytdlp_args(video_id: str, start_time: float, end_time: float, output_path: str | Path, format_spec: str = "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best") -> list[str]`:
   - Monta lista de argumentos CLI para o `yt-dlp`:
     - `--download-sections` no formato `*START-END`
     - `--force-keyframes-at-cuts` (para corte preciso sem telas congeladas)
     - `-f` com especificação de qualidade
     - `-o` com o caminho de saída
     - URL completa do YouTube `https://www.youtube.com/watch?v={video_id}`

3. Classe `SurgicalDownloader`:
   - `__init__(self, temp_dir: Path | str = None)`
   - `download_segment(video_id: str, start_time: float, end_time: float, output_filename: str = None) -> Path`:
     - Executa o download de forma controlada (via `subprocess.run` ou API Python `yt_dlp.YoutubeDL`).
     - Cria o diretório de destino se não existir.
     - Valida se o arquivo gerado realmente existe e possui tamanho > 0.
     - Trata exceções com `DownloadError` customizado em caso de falha de download, timeout ou vídeo privado.

## Testes (`tests/test_downloader.py`)
- Testar `format_time_sec_to_hms` para vários valores (0s, 65.5s, 3605s).
- Testar `build_ytdlp_args` garantindo presença do argumento `--download-sections`, formato correto dos timestamps e caminho de saída.
- Testar `SurgicalDownloader.download_segment` utilizando mocks de subprocess/YoutubeDL para simular sucesso, erro de execução e timeout sem precisar fazer download real de vídeo de rede durante a suíte de testes.

## Critérios de Aceite
- Executar `pytest tests/test_downloader.py -v` com 100% de sucesso.
- Executar toda a suíte `pytest tests/` garantindo zero regressões.
- Git commit: `feat: surgical clip downloader with yt-dlp`.
