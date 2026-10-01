import os
from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações globais do pipeline AutoShorts."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    BASE_DIR: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent)
    STORAGE_DIR: Optional[Path] = None
    TEMP_DIR: Optional[Path] = None
    OUTPUT_DIR: Optional[Path] = None
    DB_PATH: Optional[Path] = None

    POLL_INTERVAL_MINUTES: int = 60
    POST_INTERVAL_HOURS: int = 4
    MAX_CLIPS_PER_VIDEO: int = 3
    MIN_CLIP_DURATION: int = 45
    MAX_CLIP_DURATION: int = 90

    GEMINI_API_KEY: str = ""
    YOUTUBE_CLIENT_SECRETS: str = "secrets/youtube_client.json"
    INSTAGRAM_ACCESS_TOKEN: str = ""
    INSTAGRAM_ACCOUNT_ID: str = ""

    def model_post_init(self, __context) -> None:
        if self.STORAGE_DIR is None:
            self.STORAGE_DIR = self.BASE_DIR / "storage"
        if self.TEMP_DIR is None:
            self.TEMP_DIR = self.STORAGE_DIR / "temp"
        if self.OUTPUT_DIR is None:
            self.OUTPUT_DIR = self.STORAGE_DIR / "output"
        if self.DB_PATH is None:
            self.DB_PATH = self.STORAGE_DIR / "pipeline.db"

        # Cria automaticamente as pastas de storage se não existirem
        self.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        self.TEMP_DIR.mkdir(parents=True, exist_ok=True)
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def __getattr__(self, name: str):
        # Permite acesso case-insensitive a atributos (ex.: settings.poll_interval_minutes)
        upper_name = name.upper()
        if upper_name in self.__dict__:
            return self.__dict__[upper_name]
        return super().__getattribute__(name)


def _ensure_ffmpeg_in_path() -> None:
    """Garante que o FFmpeg instalado no Windows seja encontrado no PATH."""
    import glob
    import shutil

    if shutil.which("ffmpeg") is not None:
        return
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        candidates = glob.glob(
            f"{local_app_data}/Microsoft/WinGet/Packages/Gyan.FFmpeg.Essentials_*/ffmpeg-*/bin"
        )
        for c in candidates:
            if os.path.exists(os.path.join(c, "ffmpeg.exe")):
                os.environ["PATH"] = c + os.pathsep + os.environ["PATH"]
                return


_ensure_ffmpeg_in_path()

# Instância padrão de configurações
settings = Settings()

