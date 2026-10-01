"""Testes unitários para publicadores headless baseados em Playwright (TikTok e Kwai)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from src.publisher.base import BasePublisher, PublishResult
from src.publisher.session_helper import validate_session_file, save_session_state
from src.publisher.tiktok import TikTokPublisher
from src.publisher.kwai import KwaiPublisher
from src.publisher import (
    TikTokPublisher as ExportedTikTokPublisher,
    KwaiPublisher as ExportedKwaiPublisher,
)


# ============================================================================
# Fixtures e Utilitários para Testes
# ============================================================================

@pytest.fixture
def temp_dirs(tmp_path):
    """Cria diretórios temporários para vídeo e segredos."""
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()
    videos_dir = tmp_path / "videos"
    videos_dir.mkdir()
    return secrets_dir, videos_dir


@pytest.fixture
def valid_session_file(temp_dirs):
    """Cria um arquivo de sessão Playwright válido."""
    secrets_dir, _ = temp_dirs
    session_file = secrets_dir / "valid_session.json"
    session_data = {
        "cookies": [
            {
                "name": "sessionid",
                "value": "fake_token_12345",
                "domain": ".tiktok.com",
                "path": "/",
                "expires": 1899999999,
                "httpOnly": True,
                "secure": True,
                "sameSite": "None",
            }
        ],
        "origins": [
            {
                "origin": "https://www.tiktok.com",
                "localStorage": [{"name": "user_id", "value": "12345"}],
            }
        ],
    }
    session_file.write_text(json.dumps(session_data), encoding="utf-8")
    return session_file


@pytest.fixture
def valid_video_file(temp_dirs):
    """Cria um arquivo de vídeo de teste simulado."""
    _, videos_dir = temp_dirs
    video_file = videos_dir / "clip_001.mp4"
    video_file.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00")
    return video_file


# ============================================================================
# 1. Testes de Validação de Sessão (session_helper)
# ============================================================================

class TestSessionHelper:
    """Testes para o utilitário de validação de arquivos de sessão Playwright."""

    def test_validate_session_nonexistent_file(self, tmp_path):
        """Arquivo inexistente deve retornar falso e mensagem apropriada."""
        missing_file = tmp_path / "nao_existe.json"
        is_valid, err = validate_session_file(missing_file)
        assert is_valid is False
        assert "not found" in err.lower() or "não encontrado" in err.lower()

    def test_validate_session_empty_file(self, tmp_path):
        """Arquivo vazio deve retornar falso."""
        empty_file = tmp_path / "empty.json"
        empty_file.write_text("", encoding="utf-8")
        is_valid, err = validate_session_file(empty_file)
        assert is_valid is False
        assert "empty" in err.lower() or "vazio" in err.lower()

    def test_validate_session_corrupted_json(self, tmp_path):
        """JSON malformado deve retornar falso."""
        bad_json = tmp_path / "corrupted.json"
        bad_json.write_text("{invalid_json: 123", encoding="utf-8")
        is_valid, err = validate_session_file(bad_json)
        assert is_valid is False
        assert "json" in err.lower()

    def test_validate_session_missing_cookies_structure(self, tmp_path):
        """JSON sem estrutura de cookies deve retornar falso."""
        invalid_structure = tmp_path / "no_cookies.json"
        invalid_structure.write_text(json.dumps({"some_key": "some_value"}), encoding="utf-8")
        is_valid, err = validate_session_file(invalid_structure)
        assert is_valid is False
        assert "cookies" in err.lower()

    def test_validate_session_valid_storage_state(self, valid_session_file):
        """Arquivo padrão Playwright com cookies e origins deve retornar verdadeiro."""
        is_valid, err = validate_session_file(valid_session_file)
        assert is_valid is True
        assert err is None

    def test_validate_session_valid_raw_cookie_list(self, tmp_path):
        """Lista direta de cookies em formato JSON também deve ser aceita."""
        cookie_list_file = tmp_path / "cookies_list.json"
        cookie_list_file.write_text(
            json.dumps([{"name": "kuaishou_sid", "value": "abcdef"}]),
            encoding="utf-8",
        )
        is_valid, err = validate_session_file(cookie_list_file)
        assert is_valid is True
        assert err is None

    def test_save_session_state(self, tmp_path):
        """Verifica que save_session_state persiste dados corretamente em JSON."""
        target_path = tmp_path / "subfolder" / "new_session.json"
        data = {"cookies": [{"name": "foo", "value": "bar"}]}
        saved = save_session_state(data, target_path)
        assert saved.exists()
        loaded = json.loads(saved.read_text(encoding="utf-8"))
        assert loaded == data


# ============================================================================
# 2. Testes de TikTokPublisher
# ============================================================================

class TestTikTokPublisher:
    """Testes unitários para o publicador headless do TikTok."""

    def test_init_defaults(self):
        """Verifica os valores padrão da inicialização do TikTokPublisher."""
        pub = TikTokPublisher()
        assert isinstance(pub, BasePublisher)
        assert Path(pub.session_path) == Path("secrets/tiktok_session.json")
        assert pub.headless is True
        assert pub.timeout_sec == 60
        assert "tiktok.com" in pub.upload_url

    def test_init_custom_parameters(self, tmp_path):
        """Verifica a configuração customizada do TikTokPublisher."""
        custom_session = tmp_path / "custom_tiktok.json"
        pub = TikTokPublisher(
            session_path=custom_session,
            headless=False,
            timeout_sec=120,
            upload_url="https://custom.tiktok.com/upload",
        )
        assert pub.session_path == custom_session
        assert pub.headless is False
        assert pub.timeout_sec == 120
        assert pub.upload_url == "https://custom.tiktok.com/upload"

    def test_publish_video_file_not_found(self, valid_session_file, tmp_path):
        """Falha se o arquivo de vídeo não existir."""
        pub = TikTokPublisher(session_path=valid_session_file)
        missing_video = tmp_path / "missing.mp4"

        result = pub.publish(video_path=missing_video, title="Meu Short")
        assert result.success is False
        assert result.platform == "tiktok"
        assert "video file not found" in result.error.lower()

    def test_publish_session_file_not_found(self, valid_video_file, tmp_path):
        """Falha se o arquivo de sessão não existir."""
        missing_session = tmp_path / "missing_session.json"
        pub = TikTokPublisher(session_path=missing_session)

        result = pub.publish(video_path=valid_video_file, title="Meu Short")
        assert result.success is False
        assert result.platform == "tiktok"
        assert "session file not found" in result.error.lower()

    def test_publish_invalid_session_file(self, valid_video_file, tmp_path):
        """Falha com mensagem informativa se a sessão for inválida/corrompida."""
        bad_session = tmp_path / "bad_session.json"
        bad_session.write_text("not json content", encoding="utf-8")
        pub = TikTokPublisher(session_path=bad_session)

        result = pub.publish(video_path=valid_video_file, title="Meu Short")
        assert result.success is False
        assert result.platform == "tiktok"
        assert "invalid session" in result.error.lower() or "json" in result.error.lower()

    def test_publish_success_flow(self, valid_session_file, valid_video_file):
        """Simula o fluxo completo de publicação com sucesso usando mocks do Playwright."""
        pub = TikTokPublisher(session_path=valid_session_file, headless=True)

        mock_page = MagicMock()
        mock_file_input = MagicMock()
        mock_caption_box = MagicMock()
        mock_post_btn = MagicMock()
        mock_success_indicator = MagicMock()

        mock_page.locator.side_effect = lambda selector: {
            'input[type="file"]': mock_file_input,
            'div[contenteditable="true"], .public-DraftEditor-content, textarea': mock_caption_box,
            'button:has-text("Post"), button:has-text("Publicar"), button.btn-post': mock_post_btn,
        }.get(selector, mock_success_indicator)

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page

        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context

        mock_chromium = MagicMock()
        mock_chromium.launch.return_value = mock_browser

        mock_playwright = MagicMock()
        mock_playwright.chromium = mock_chromium

        with patch("src.publisher.tiktok.sync_playwright") as mock_sync_pw:
            mock_sync_pw.return_value.__enter__.return_value = mock_playwright

            result = pub.publish(
                video_path=valid_video_file,
                title="Curiosidade Incrível",
                description="Veja até o final!",
                hashtags=["curiosidades", "fatos"],
            )

        assert result.success is True
        assert result.platform == "tiktok"
        assert result.post_id is not None
        assert result.url is not None
        assert result.error is None

        # Verificações dos métodos chamados
        mock_chromium.launch.assert_called_once_with(headless=True)
        mock_browser.new_context.assert_called_once_with(storage_state=str(valid_session_file))
        mock_page.goto.assert_called_once()
        mock_file_input.set_input_files.assert_called_once_with(str(valid_video_file.resolve()))
        mock_caption_box.fill.assert_called_once()
        mock_post_btn.click.assert_called_once()
        mock_browser.close.assert_called_once()

    def test_publish_timeout_error_handling(self, valid_session_file, valid_video_file):
        """Verifica captura e retorno seguro quando ocorre Timeout do Playwright."""
        pub = TikTokPublisher(session_path=valid_session_file, timeout_sec=5)

        mock_page = MagicMock()
        mock_page.goto.side_effect = TimeoutError("Timeout 5000ms exceeded navigating to upload")

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page

        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context

        mock_chromium = MagicMock()
        mock_chromium.launch.return_value = mock_browser

        mock_playwright = MagicMock()
        mock_playwright.chromium = mock_chromium

        with patch("src.publisher.tiktok.sync_playwright") as mock_sync_pw:
            mock_sync_pw.return_value.__enter__.return_value = mock_playwright

            result = pub.publish(video_path=valid_video_file, title="Vídeo Teste")

        assert result.success is False
        assert result.platform == "tiktok"
        assert "timeout" in result.error.lower()
        mock_browser.close.assert_called_once()

    def test_publish_general_exception_handling(self, valid_session_file, valid_video_file):
        """Verifica captura de erro genérico (ex: seletor não encontrado ou crash do browser)."""
        pub = TikTokPublisher(session_path=valid_session_file)

        mock_page = MagicMock()
        mock_file_input = MagicMock()
        mock_file_input.set_input_files.side_effect = RuntimeError("Element not interactable")
        mock_page.locator.return_value = mock_file_input

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_chromium = MagicMock()
        mock_chromium.launch.return_value = mock_browser
        mock_playwright = MagicMock()
        mock_playwright.chromium = mock_chromium

        with patch("src.publisher.tiktok.sync_playwright") as mock_sync_pw:
            mock_sync_pw.return_value.__enter__.return_value = mock_playwright

            result = pub.publish(video_path=valid_video_file, title="Vídeo Teste")

        assert result.success is False
        assert result.platform == "tiktok"
        assert "not interactable" in result.error.lower()
        mock_browser.close.assert_called_once()

    def test_publish_missing_playwright_dependency(self, valid_session_file, valid_video_file):
        """Retorna erro amigável se Playwright não estiver disponível."""
        pub = TikTokPublisher(session_path=valid_session_file)
        with patch("src.publisher.tiktok.sync_playwright", None):
            result = pub.publish(video_path=valid_video_file, title="Teste Sem PW")

        assert result.success is False
        assert result.platform == "tiktok"
        assert "playwright is not installed" in result.error.lower()

    def test_publish_iframe_upload_fallback(self, valid_session_file, valid_video_file):
        """Testa fallback de upload quando input[type='file'] está dentro de iframe."""
        pub = TikTokPublisher(session_path=valid_session_file)

        mock_page = MagicMock()
        mock_file_main = MagicMock()
        mock_file_main.wait_for.side_effect = RuntimeError("Not found on main page")

        mock_frame = MagicMock()
        mock_frame_file = MagicMock()
        mock_frame_file.count.return_value = 1
        mock_frame.locator.return_value = mock_frame_file
        mock_page.frames = [mock_frame]

        mock_caption_box = MagicMock()
        mock_post_btn = MagicMock()

        mock_page.locator.side_effect = lambda selector: {
            'input[type="file"]': mock_file_main,
            'div[contenteditable="true"], .public-DraftEditor-content, textarea': mock_caption_box,
            'button:has-text("Post"), button:has-text("Publicar"), button.btn-post': mock_post_btn,
        }.get(selector, MagicMock())

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_chromium = MagicMock()
        mock_chromium.launch.return_value = mock_browser
        mock_playwright = MagicMock()
        mock_playwright.chromium = mock_chromium

        with patch("src.publisher.tiktok.sync_playwright") as mock_sync_pw:
            mock_sync_pw.return_value.__enter__.return_value = mock_playwright
            result = pub.publish(video_path=valid_video_file, title="Vídeo Frame")

        assert result.success is True
        assert result.platform == "tiktok"
        mock_frame_file.set_input_files.assert_called_once_with(str(valid_video_file.resolve()))

    def test_publish_caption_fill_fallback_to_type(self, valid_session_file, valid_video_file):
        """Testa fallback para page.keyboard.type quando fill falha no TikTok."""
        pub = TikTokPublisher(session_path=valid_session_file)

        mock_page = MagicMock()
        mock_file_input = MagicMock()
        mock_caption_box = MagicMock()
        mock_caption_box.fill.side_effect = RuntimeError("Fill not supported")
        mock_post_btn = MagicMock()

        mock_page.locator.side_effect = lambda selector: {
            'input[type="file"]': mock_file_input,
            'div[contenteditable="true"], .public-DraftEditor-content, textarea': mock_caption_box,
            'button:has-text("Post"), button:has-text("Publicar"), button.btn-post': mock_post_btn,
        }.get(selector, MagicMock())

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_chromium = MagicMock()
        mock_chromium.launch.return_value = mock_browser
        mock_playwright = MagicMock()
        mock_playwright.chromium = mock_chromium

        with patch("src.publisher.tiktok.sync_playwright") as mock_sync_pw:
            mock_sync_pw.return_value.__enter__.return_value = mock_playwright
            result = pub.publish(video_path=valid_video_file, title="Vídeo Type")

        assert result.success is True
        assert result.platform == "tiktok"
        mock_page.keyboard.type.assert_called_once()


# ============================================================================
# 3. Testes de KwaiPublisher
# ============================================================================

class TestKwaiPublisher:
    """Testes unitários para o publicador headless do Kwai."""

    def test_init_defaults(self):
        """Verifica valores padrão da inicialização do KwaiPublisher."""
        pub = KwaiPublisher()
        assert isinstance(pub, BasePublisher)
        assert Path(pub.session_path) == Path("secrets/kwai_session.json")
        assert pub.headless is True
        assert pub.timeout_sec == 60
        assert "kwai.com" in pub.upload_url

    def test_init_custom_parameters(self, tmp_path):
        """Verifica configuração customizada do KwaiPublisher."""
        custom_session = tmp_path / "custom_kwai.json"
        pub = KwaiPublisher(
            session_path=custom_session,
            headless=False,
            timeout_sec=90,
            upload_url="https://creator.kwai.com/custom_upload",
        )
        assert pub.session_path == custom_session
        assert pub.headless is False
        assert pub.timeout_sec == 90
        assert pub.upload_url == "https://creator.kwai.com/custom_upload"

    def test_publish_video_file_not_found(self, valid_session_file, tmp_path):
        """Falha se o arquivo de vídeo não existir."""
        pub = KwaiPublisher(session_path=valid_session_file)
        missing_video = tmp_path / "missing_kwai.mp4"

        result = pub.publish(video_path=missing_video, title="Meu Kwai")
        assert result.success is False
        assert result.platform == "kwai"
        assert "video file not found" in result.error.lower()

    def test_publish_session_file_not_found(self, valid_video_file, tmp_path):
        """Falha se o arquivo de sessão do Kwai não existir."""
        missing_session = tmp_path / "missing_kwai_session.json"
        pub = KwaiPublisher(session_path=missing_session)

        result = pub.publish(video_path=valid_video_file, title="Meu Kwai")
        assert result.success is False
        assert result.platform == "kwai"
        assert "session file not found" in result.error.lower()

    def test_publish_invalid_session_file(self, valid_video_file, tmp_path):
        """Falha com mensagem clara se o JSON da sessão estiver corrompido."""
        bad_session = tmp_path / "bad_kwai.json"
        bad_session.write_text("{corrupt: true", encoding="utf-8")
        pub = KwaiPublisher(session_path=bad_session)

        result = pub.publish(video_path=valid_video_file, title="Meu Kwai")
        assert result.success is False
        assert result.platform == "kwai"
        assert "invalid session" in result.error.lower() or "json" in result.error.lower()

    def test_publish_success_flow(self, valid_session_file, valid_video_file):
        """Simula o fluxo completo de publicação com sucesso no Kwai usando mocks."""
        pub = KwaiPublisher(session_path=valid_session_file, headless=True)

        mock_page = MagicMock()
        mock_file_input = MagicMock()
        mock_caption_box = MagicMock()
        mock_publish_btn = MagicMock()
        mock_success_indicator = MagicMock()

        mock_page.locator.side_effect = lambda selector: {
            'input[type="file"]': mock_file_input,
            'textarea, div[contenteditable="true"], input[placeholder*="título"], input[placeholder*="title"]': mock_caption_box,
            'button:has-text("Publicar"), button:has-text("Publish"), button:has-text("Post")': mock_publish_btn,
        }.get(selector, mock_success_indicator)

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page

        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context

        mock_chromium = MagicMock()
        mock_chromium.launch.return_value = mock_browser

        mock_playwright = MagicMock()
        mock_playwright.chromium = mock_chromium

        with patch("src.publisher.kwai.sync_playwright") as mock_sync_pw:
            mock_sync_pw.return_value.__enter__.return_value = mock_playwright

            result = pub.publish(
                video_path=valid_video_file,
                title="Super Dica Kwai",
                description="Assista e compartilhe!",
                hashtags=["kwai", "viral"],
            )

        assert result.success is True
        assert result.platform == "kwai"
        assert result.post_id is not None
        assert result.url is not None
        assert result.error is None

        # Verificações dos métodos
        mock_chromium.launch.assert_called_once_with(headless=True)
        mock_browser.new_context.assert_called_once_with(storage_state=str(valid_session_file))
        mock_page.goto.assert_called_once_with(pub.upload_url, wait_until="domcontentloaded")
        mock_file_input.set_input_files.assert_called_once_with(str(valid_video_file.resolve()))
        mock_caption_box.fill.assert_called_once()
        mock_publish_btn.click.assert_called_once()
        mock_browser.close.assert_called_once()

    def test_publish_timeout_error_handling(self, valid_session_file, valid_video_file):
        """Verifica captura de timeout na página de upload do Kwai."""
        pub = KwaiPublisher(session_path=valid_session_file, timeout_sec=10)

        mock_page = MagicMock()
        mock_page.goto.side_effect = TimeoutError("Timeout Kwai navigation")

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_chromium = MagicMock()
        mock_chromium.launch.return_value = mock_browser
        mock_playwright = MagicMock()
        mock_playwright.chromium = mock_chromium

        with patch("src.publisher.kwai.sync_playwright") as mock_sync_pw:
            mock_sync_pw.return_value.__enter__.return_value = mock_playwright

            result = pub.publish(video_path=valid_video_file, title="Vídeo Teste Kwai")

        assert result.success is False
        assert result.platform == "kwai"
        assert "timeout" in result.error.lower()
        mock_browser.close.assert_called_once()

    def test_publish_general_exception_handling(self, valid_session_file, valid_video_file):
        """Verifica tratamento de exceção genérica no Kwai."""
        pub = KwaiPublisher(session_path=valid_session_file)

        mock_page = MagicMock()
        mock_page.locator.side_effect = RuntimeError("Kwai selector missing")

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_chromium = MagicMock()
        mock_chromium.launch.return_value = mock_browser
        mock_playwright = MagicMock()
        mock_playwright.chromium = mock_chromium

        with patch("src.publisher.kwai.sync_playwright") as mock_sync_pw:
            mock_sync_pw.return_value.__enter__.return_value = mock_playwright

            result = pub.publish(video_path=valid_video_file, title="Vídeo Teste Kwai")

        assert result.success is False
        assert result.platform == "kwai"
        assert "selector missing" in result.error.lower()
        mock_browser.close.assert_called_once()

    def test_publish_missing_playwright_dependency(self, valid_session_file, valid_video_file):
        """Retorna erro amigável se Playwright não estiver instalado no Kwai."""
        pub = KwaiPublisher(session_path=valid_session_file)
        with patch("src.publisher.kwai.sync_playwright", None):
            result = pub.publish(video_path=valid_video_file, title="Teste Sem PW Kwai")

        assert result.success is False
        assert result.platform == "kwai"
        assert "playwright is not installed" in result.error.lower()

    def test_publish_iframe_upload_fallback(self, valid_session_file, valid_video_file):
        """Testa fallback de upload quando input de arquivo no Kwai está dentro de iframe."""
        pub = KwaiPublisher(session_path=valid_session_file)

        mock_page = MagicMock()
        mock_file_main = MagicMock()
        mock_file_main.wait_for.side_effect = RuntimeError("Not found on Kwai main page")

        mock_frame = MagicMock()
        mock_frame_file = MagicMock()
        mock_frame_file.count.return_value = 1
        mock_frame.locator.return_value = mock_frame_file
        mock_page.frames = [mock_frame]

        mock_caption_box = MagicMock()
        mock_publish_btn = MagicMock()

        mock_page.locator.side_effect = lambda selector: {
            'input[type="file"]': mock_file_main,
            'textarea, div[contenteditable="true"], input[placeholder*="título"], input[placeholder*="title"]': mock_caption_box,
            'button:has-text("Publicar"), button:has-text("Publish"), button:has-text("Post")': mock_publish_btn,
        }.get(selector, MagicMock())

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_chromium = MagicMock()
        mock_chromium.launch.return_value = mock_browser
        mock_playwright = MagicMock()
        mock_playwright.chromium = mock_chromium

        with patch("src.publisher.kwai.sync_playwright") as mock_sync_pw:
            mock_sync_pw.return_value.__enter__.return_value = mock_playwright
            result = pub.publish(video_path=valid_video_file, title="Vídeo Frame Kwai")

        assert result.success is True
        assert result.platform == "kwai"
        mock_frame_file.set_input_files.assert_called_once_with(str(valid_video_file.resolve()))

    def test_publish_caption_fill_fallback_to_type(self, valid_session_file, valid_video_file):
        """Testa fallback para page.keyboard.type quando fill falha no Kwai."""
        pub = KwaiPublisher(session_path=valid_session_file)

        mock_page = MagicMock()
        mock_file_input = MagicMock()
        mock_caption_box = MagicMock()
        mock_caption_box.fill.side_effect = RuntimeError("Fill failed on Kwai")
        mock_publish_btn = MagicMock()

        mock_page.locator.side_effect = lambda selector: {
            'input[type="file"]': mock_file_input,
            'textarea, div[contenteditable="true"], input[placeholder*="título"], input[placeholder*="title"]': mock_caption_box,
            'button:has-text("Publicar"), button:has-text("Publish"), button:has-text("Post")': mock_publish_btn,
        }.get(selector, MagicMock())

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_chromium = MagicMock()
        mock_chromium.launch.return_value = mock_browser
        mock_playwright = MagicMock()
        mock_playwright.chromium = mock_chromium

        with patch("src.publisher.kwai.sync_playwright") as mock_sync_pw:
            mock_sync_pw.return_value.__enter__.return_value = mock_playwright
            result = pub.publish(video_path=valid_video_file, title="Vídeo Type Kwai")

        assert result.success is True
        assert result.platform == "kwai"
        mock_page.keyboard.type.assert_called_once()


# ============================================================================
# 4. Testes de Exportação do Pacote
# ============================================================================

class TestPublisherExports:
    """Verifica que as classes públicas são exportadas pelo pacote src.publisher."""

    def test_exports_available(self):
        """Garante que TikTokPublisher e KwaiPublisher estão no __all__ de src.publisher."""
        assert ExportedTikTokPublisher is TikTokPublisher
        assert ExportedKwaiPublisher is KwaiPublisher
        assert issubclass(TikTokPublisher, BasePublisher)
        assert issubclass(KwaiPublisher, BasePublisher)
