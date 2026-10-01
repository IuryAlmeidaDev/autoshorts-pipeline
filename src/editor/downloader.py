"""Módulo de download cirúrgico de segmentos de vídeo utilizando yt-dlp."""

import logging
from pathlib import Path
import subprocess
from typing import Optional, Union

from src.config import settings

logger = logging.getLogger(__name__)

DEFAULT_FORMAT_SPEC = (
    "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best"
)


class DownloadError(Exception):
    """Exceção levantada em falhas durante o download cirúrgico com yt-dlp."""

    def __init__(self, message: str, video_id: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.video_id = video_id


def format_time_sec_to_hms(seconds: float) -> str:
    """Converte segundos decimais em string formatada HH:MM:SS.mmm.

    Exemplos:
        0.0 -> '00:00:00.000'
        65.5 -> '00:01:05.500'
        84.5 -> '00:01:24.500'
        3605.0 -> '01:00:05.000'
    """
    total_millis = round(max(0.0, float(seconds)) * 1000)
    hours = total_millis // 3_600_000
    rem = total_millis % 3_600_000
    minutes = rem // 60_000
    rem = rem % 60_000
    secs = rem // 1000
    millis = rem % 1000

    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def build_ytdlp_args(
    video_id: str,
    start_time: float,
    end_time: float,
    output_path: Union[str, Path],
    format_spec: str = DEFAULT_FORMAT_SPEC,
    extra_args: Optional[list[str]] = None,
) -> list[str]:
    """Monta a lista de argumentos de linha de comando para o yt-dlp.

    Argumentos incluídos:
      - --download-sections: *START-END
      - --force-keyframes-at-cuts
      - -f: especificação de qualidade
      - -o: caminho de saída
      - URL completa do YouTube
    """
    if not video_id or not str(video_id).strip():
        raise ValueError("video_id cannot be empty")
    if start_time < 0:
        raise ValueError(f"start_time ({start_time}) must be >= 0")
    if end_time <= start_time:
        raise ValueError(
            f"end_time ({end_time}) must be greater than start_time ({start_time})"
        )

    start_str = format_time_sec_to_hms(start_time)
    end_str = format_time_sec_to_hms(end_time)
    url = f"https://www.youtube.com/watch?v={video_id.strip()}"

    args = [
        "--download-sections",
        f"*{start_str}-{end_str}",
        "--force-keyframes-at-cuts",
        "-f",
        format_spec,
        "-o",
        str(output_path),
        url,
    ]

    if extra_args:
        args.extend(extra_args)

    return args


class SurgicalDownloader:
    """Baixador cirúrgico de trechos de vídeo sem necessidade de baixar o arquivo completo."""

    def __init__(
        self,
        temp_dir: Optional[Union[Path, str]] = None,
        format_spec: str = DEFAULT_FORMAT_SPEC,
        timeout: int = 300,
        executable: Optional[str] = None,
        method: str = "subprocess",
    ):
        """Inicializa o SurgicalDownloader.

        Args:
            temp_dir: Diretório para armazenamento temporário de downloads.
            format_spec: String de seleção de formato para o yt-dlp.
            timeout: Tempo limite em segundos para o processo de download.
            executable: Nome ou caminho do executável yt-dlp (padrão 'yt-dlp').
            method: Modo de download ('subprocess' ou 'api').
        """
        if temp_dir is None:
            self.temp_dir = settings.TEMP_DIR
        else:
            self.temp_dir = Path(temp_dir)

        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.format_spec = format_spec
        self.timeout = timeout
        self.executable = executable or "yt-dlp"
        self.method = method.lower()

    def download_segment(
        self,
        video_id: str,
        start_time: float,
        end_time: float,
        output_filename: Optional[str] = None,
    ) -> Path:
        """Baixa o intervalo cirúrgico especificado do vídeo.

        Args:
            video_id: ID do vídeo no YouTube.
            start_time: Ponto inicial em segundos.
            end_time: Ponto final em segundos.
            output_filename: Nome ou caminho de arquivo opcional.

        Returns:
            Path para o arquivo de vídeo baixado e verificado.

        Raises:
            ValueError: Se os parâmetros de tempo ou ID forem inválidos.
            DownloadError: Em caso de falha de download, timeout ou vídeo privado.
        """
        if not video_id or not str(video_id).strip():
            raise ValueError("video_id cannot be empty")
        if start_time < 0 or end_time <= start_time:
            raise ValueError(
                f"Invalid time range: start={start_time}, end={end_time}. "
                "start_time must be >= 0 and end_time > start_time."
            )

        clean_id = video_id.strip()

        # Determina o caminho de saída
        if output_filename:
            candidate = Path(output_filename)
            dest_path = candidate if candidate.is_absolute() else self.temp_dir / candidate
        else:
            dest_path = self.temp_dir / f"{clean_id}_{int(start_time)}_{int(end_time)}.mp4"

        dest_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Iniciando download cirúrgico: video=%s [%s -> %s] -> %s (modo: %s)",
            clean_id,
            start_time,
            end_time,
            dest_path,
            self.method,
        )

        if self.method == "api":
            self._download_via_api(clean_id, start_time, end_time, dest_path)
        else:
            self._download_via_subprocess(clean_id, start_time, end_time, dest_path)

        final_file = self._verify_output_file(dest_path)
        if final_file is None:
            raise DownloadError(
                f"Downloaded file '{dest_path}' was not created or is empty",
                video_id=clean_id,
            )

        logger.info("Download cirúrgico concluído com sucesso: %s", final_file)
        return final_file

    def _download_via_subprocess(
        self,
        video_id: str,
        start_time: float,
        end_time: float,
        output_path: Path,
    ) -> None:
        """Executa o download utilizando subprocess chamando yt-dlp."""
        args = build_ytdlp_args(
            video_id=video_id,
            start_time=start_time,
            end_time=end_time,
            output_path=output_path,
            format_spec=self.format_spec,
        )
        cmd = [self.executable] + args

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise DownloadError(
                f"Download timed out after {self.timeout}s for video '{video_id}'",
                video_id=video_id,
            ) from exc
        except FileNotFoundError as exc:
            raise DownloadError(
                f"Executable '{self.executable}' not found: {exc}",
                video_id=video_id,
            ) from exc
        except Exception as exc:
            raise DownloadError(
                f"Unexpected subprocess error: {exc}",
                video_id=video_id,
            ) from exc

        if result.returncode != 0:
            stderr = result.stderr or ""
            stdout = result.stdout or ""
            combined = f"{stderr}\n{stdout}".strip()

            if "private video" in combined.lower() or "video is private" in combined.lower():
                raise DownloadError(
                    f"Video '{video_id}' is private or inaccessible: {combined}",
                    video_id=video_id,
                )

            raise DownloadError(
                f"Download failed with exit code {result.returncode}: {combined}",
                video_id=video_id,
            )

    def _download_via_api(
        self,
        video_id: str,
        start_time: float,
        end_time: float,
        output_path: Path,
    ) -> None:
        """Executa o download utilizando a biblioteca Python yt_dlp."""
        try:
            import yt_dlp
            from yt_dlp.utils import download_range_func
        except ImportError as exc:
            raise DownloadError(
                f"yt_dlp package is not available for API mode: {exc}",
                video_id=video_id,
            ) from exc

        ydl_opts = {
            "format": self.format_spec,
            "outtmpl": str(output_path),
            "download_ranges": download_range_func(None, [(start_time, end_time)]),
            "force_keyframes_at_cuts": True,
            "quiet": True,
            "no_warnings": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                url = f"https://www.youtube.com/watch?v={video_id}"
                ydl.download([url])
        except Exception as exc:
            err_msg = str(exc)
            if "private video" in err_msg.lower() or "video is private" in err_msg.lower():
                raise DownloadError(
                    f"Video '{video_id}' is private or inaccessible: {err_msg}",
                    video_id=video_id,
                ) from exc
            raise DownloadError(
                f"yt-dlp API error: {err_msg}",
                video_id=video_id,
            ) from exc

    @staticmethod
    def _verify_output_file(dest_path: Path) -> Optional[Path]:
        """Verifica se o arquivo de destino ou derivado foi criado e possui tamanho > 0."""
        if dest_path.exists() and dest_path.stat().st_size > 0:
            return dest_path

        # Caso o yt-dlp tenha alterado a extensão (ex.: .mkv, .webm)
        if dest_path.parent.exists():
            candidates = [
                f
                for f in dest_path.parent.glob(f"{dest_path.stem}*")
                if f.is_file() and f.stat().st_size > 0
            ]
            if candidates:
                for c in candidates:
                    if c.suffix.lower() == ".mp4":
                        return c
                return candidates[0]

        return None
