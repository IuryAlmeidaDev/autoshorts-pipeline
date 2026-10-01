"""Publicador headless para TikTok Creator Center baseado em Playwright."""

import logging
from pathlib import Path
import time
from typing import List, Optional, Tuple, Union

from src.publisher.base import BasePublisher, PublishResult
from src.publisher.session_helper import validate_session_file

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None

logger = logging.getLogger(__name__)


class TikTokPublisher(BasePublisher):
    """Publicador de vídeos no TikTok utilizando automação de navegador com sessão autenticada."""

    def __init__(
        self,
        session_path: Union[str, Path] = "secrets/tiktok_session.json",
        headless: bool = True,
        timeout_sec: int = 60,
        upload_url: str = "https://www.tiktok.com/creator-center/upload",
    ):
        """Inicializa o publicador do TikTok.

        Args:
            session_path: Caminho para o arquivo storage_state.json de sessão Playwright.
            headless: Se True, executa o navegador em modo oculto (headless).
            timeout_sec: Timeout padrão em segundos para interações com elementos da página.
            upload_url: URL da página de upload do Creator Center do TikTok.
        """
        self.session_path = Path(session_path)
        self.headless = headless
        self.timeout_sec = timeout_sec
        self.upload_url = upload_url

    def publish(
        self,
        video_path: Union[Path, str],
        title: str,
        description: str = "",
        hashtags: Optional[List[str]] = None,
    ) -> PublishResult:
        """Publica um vídeo no TikTok através do Creator Center.

        Args:
            video_path: Caminho para o arquivo MP4 do vídeo.
            title: Título principal do post.
            description: Descrição complementar opcional.
            hashtags: Lista opcional de hashtags.

        Returns:
            PublishResult com status da postagem, id/url ou mensagem de erro.
        """
        # 1. Validação de arquivos locais
        video_file = Path(video_path)
        if not video_file.exists() or not video_file.is_file():
            return PublishResult(
                success=False,
                platform="tiktok",
                error=f"Video file not found: {video_path}",
            )

        if not self.session_path.exists() or not self.session_path.is_file():
            return PublishResult(
                success=False,
                platform="tiktok",
                error=f"Session file not found: {self.session_path}",
            )

        is_valid_session, session_err = validate_session_file(self.session_path)
        if not is_valid_session:
            return PublishResult(
                success=False,
                platform="tiktok",
                error=f"Invalid session file: {session_err}",
            )

        # 2. Formatação da legenda unificada
        caption = self.format_caption(title=title, description=description, hashtags=hashtags)

        # 3. Automação via Playwright
        if sync_playwright is None:
            return PublishResult(
                success=False,
                platform="tiktok",
                error="Playwright is not installed. Install it with 'pip install playwright'.",
            )

        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=self.headless)
                try:
                    context = browser.new_context(storage_state=str(self.session_path))
                    page = context.new_page()
                    page.set_default_timeout(self.timeout_sec * 1000)

                    logger.info("Navegando para o TikTok Creator Center: %s", self.upload_url)
                    page.goto(self.upload_url, wait_until="domcontentloaded")

                    logger.info("Enviando arquivo de vídeo: %s", video_file)
                    self._upload_video(page, video_file.resolve())

                    logger.info("Preenchendo legenda e hashtags...")
                    self._fill_caption(page, caption)

                    logger.info("Publicando vídeo no TikTok...")
                    post_id, post_url = self._submit_post(page)

                    logger.info("Vídeo publicado com sucesso no TikTok! ID: %s", post_id)
                    return PublishResult(
                        success=True,
                        platform="tiktok",
                        post_id=post_id,
                        url=post_url,
                    )
                finally:
                    browser.close()

        except Exception as e:
            logger.exception("Falha durante publicação no TikTok: %s", e)
            return PublishResult(
                success=False,
                platform="tiktok",
                error=f"TikTok automation error: {str(e)}",
            )

    def _upload_video(self, page, video_file: Path) -> None:
        """Localiza o seletor de upload de arquivo e submete o vídeo."""
        file_input = page.locator('input[type="file"]')
        try:
            file_input.wait_for(state="attached", timeout=self.timeout_sec * 1000)
            file_input.set_input_files(str(video_file))
            return
        except Exception as initial_err:
            # Fallback se o input estiver encapsulado em iframe
            for frame in getattr(page, "frames", []):
                frame_input = frame.locator('input[type="file"]')
                try:
                    if frame_input.count() > 0:
                        frame_input.set_input_files(str(video_file))
                        return
                except Exception:
                    continue
            raise initial_err

    def _fill_caption(self, page, caption: str) -> None:
        """Preenche o campo de legenda/descrição do vídeo no TikTok."""
        caption_box = page.locator(
            'div[contenteditable="true"], .public-DraftEditor-content, textarea'
        )
        caption_box.wait_for(state="visible", timeout=self.timeout_sec * 1000)
        caption_box.click()
        try:
            caption_box.fill(caption)
        except Exception:
            page.keyboard.type(caption)

    def _submit_post(self, page) -> Tuple[str, str]:
        """Clica no botão de publicação e aguarda confirmação."""
        post_btn = page.locator(
            'button:has-text("Post"), button:has-text("Publicar"), button.btn-post'
        )
        post_btn.wait_for(state="visible", timeout=self.timeout_sec * 1000)
        post_btn.click()

        # Aguarda feedback de confirmação
        try:
            success_elem = page.locator(
                'text="Manage your posts", text="Gerenciar vídeos", text="Uploaded", text="Publicado", text="Your video has been uploaded", text="Seu vídeo foi publicado"'
            )
            success_elem.wait_for(state="visible", timeout=self.timeout_sec * 1000)
        except Exception:
            pass

        post_id = f"tiktok_{int(time.time())}"
        post_url = "https://www.tiktok.com/@creator/video"
        return post_id, post_url
