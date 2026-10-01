from pathlib import Path
import pytest
from src.config import Settings


def test_settings_load_defaults():
    settings = Settings()
    assert settings.STORAGE_DIR is not None
    assert settings.POLL_INTERVAL_MINUTES == 60
    assert settings.POST_INTERVAL_HOURS == 4
    assert settings.MAX_CLIPS_PER_VIDEO == 3
    assert settings.MIN_CLIP_DURATION == 45
    assert settings.MAX_CLIP_DURATION == 90
    assert settings.YOUTUBE_CLIENT_SECRETS == "secrets/youtube_client.json"


def test_storage_directories_auto_created(tmp_path):
    custom_storage = tmp_path / "custom_storage"
    custom_temp = custom_storage / "temp"
    custom_output = custom_storage / "output"
    
    assert not custom_temp.exists()
    assert not custom_output.exists()

    settings = Settings(
        STORAGE_DIR=custom_storage,
        TEMP_DIR=custom_temp,
        OUTPUT_DIR=custom_output,
    )

    assert settings.STORAGE_DIR.exists()
    assert settings.TEMP_DIR.exists()
    assert settings.OUTPUT_DIR.exists()


def test_settings_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("POLL_INTERVAL_MINUTES", "15")
    monkeypatch.setenv("POST_INTERVAL_HOURS", "2")
    monkeypatch.setenv("MAX_CLIPS_PER_VIDEO", "5")
    monkeypatch.setenv("MIN_CLIP_DURATION", "30")
    monkeypatch.setenv("MAX_CLIP_DURATION", "60")
    monkeypatch.setenv("GEMINI_API_KEY", "test_gemini_key")
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "test_ig_token")
    monkeypatch.setenv("INSTAGRAM_ACCOUNT_ID", "test_ig_account")

    settings = Settings(STORAGE_DIR=tmp_path / "storage")

    assert settings.POLL_INTERVAL_MINUTES == 15
    assert settings.POST_INTERVAL_HOURS == 2
    assert settings.MAX_CLIPS_PER_VIDEO == 5
    assert settings.MIN_CLIP_DURATION == 30
    assert settings.MAX_CLIP_DURATION == 60
    assert settings.GEMINI_API_KEY == "test_gemini_key"
    assert settings.INSTAGRAM_ACCESS_TOKEN == "test_ig_token"
    assert settings.INSTAGRAM_ACCOUNT_ID == "test_ig_account"
