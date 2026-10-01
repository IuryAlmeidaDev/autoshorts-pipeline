"""Módulo de publicação no Instagram Reels através da Meta Graph API."""

import logging
from pathlib import Path
import time
from typing import List, Optional, Union
import requests

from src.config import settings
from src.publisher.base import BasePublisher, PublishResult

logger = logging.getLogger(__name__)


class InstagramReelsPublisher(BasePublisher):
    """Publicador oficial para Instagram Reels via Meta Graph API."""

    def __init__(
        self,
        access_token: str = "",
        instagram_account_id: str = "",
        api_version: str = "v19.0",
        session: Optional[requests.Session] = None,
        poll_interval_seconds: float = 2.0,
        max_poll_attempts: int = 30,
    ):
        """Inicializa o publicador do Instagram Reels.

        Args:
            access_token: Token de acesso OAuth da Meta (User/Page Access Token com permissões instagram_content_publish).
            instagram_account_id: ID da conta profissional do Instagram conectada.
            api_version: Versão da Graph API (padrão v19.0).
            session: Sessão HTTP opcional para injeção e testes.
            poll_interval_seconds: Intervalo em segundos entre verificações de status do container.
            max_poll_attempts: Número máximo de tentativas de polling antes de abortar por timeout.
        """
        self.access_token = access_token or settings.INSTAGRAM_ACCESS_TOKEN
        self.instagram_account_id = instagram_account_id or settings.INSTAGRAM_ACCOUNT_ID
        self.api_version = api_version
        self.session = session or requests.Session()
        self.poll_interval_seconds = poll_interval_seconds
        self.max_poll_attempts = max_poll_attempts

        self.graph_base_url = f"https://graph.facebook.com/{self.api_version}"

    def _extract_error_message(self, response: requests.Response) -> str:
        """Extrai a mensagem de erro estruturada da resposta da Meta Graph API se disponível."""
        try:
            data = response.json()
            if isinstance(data, dict) and "error" in data:
                err = data["error"]
                if isinstance(err, dict):
                    msg = err.get("message", "")
                    code = err.get("code", "")
                    err_type = err.get("type", "")
                    return f"Meta API Error ({code} {err_type}): {msg}".strip()
                return str(err)
        except Exception:
            pass
        return response.text or f"HTTP {response.status_code}"

    def publish(
        self,
        video_path: Union[Path, str],
        title: str,
        description: str = "",
        hashtags: Optional[List[str]] = None,
    ) -> PublishResult:
        """Executa o ciclo de vida completo de publicação de Reels na Meta Graph API:
        1. Criação do container de mídia resumable.
        2. Upload binário dos bytes do arquivo de vídeo.
        3. Polling de verificação de status até FINISHED.
        4. Publicação definitiva do Reel.
        """
        if not self.access_token or not self.instagram_account_id:
            return PublishResult(
                success=False,
                platform="instagram_reels",
                error="Credenciais ausentes: access_token e instagram_account_id são obrigatórios.",
            )

        path = Path(video_path)
        if not path.is_file():
            return PublishResult(
                success=False,
                platform="instagram_reels",
                error=f"Arquivo de vídeo não encontrado: {video_path}",
            )

        caption = self.format_caption(title=title, description=description, hashtags=hashtags)

        try:
            # 1. Criação do container de mídia
            container_url = f"{self.graph_base_url}/{self.instagram_account_id}/media"
            container_payload = {
                "media_type": "REELS",
                "caption": caption,
                "upload_type": "resumable",
                "access_token": self.access_token,
            }

            resp_container = self.session.post(container_url, data=container_payload, timeout=30)
            if resp_container.status_code != 200:
                err_msg = self._extract_error_message(resp_container)
                return PublishResult(
                    success=False,
                    platform="instagram_reels",
                    error=f"Falha ao criar container do Reel: {err_msg}",
                )

            container_data = resp_container.json()
            container_id = container_data.get("id")
            upload_uri = container_data.get("uri")

            if not container_id or not upload_uri:
                return PublishResult(
                    success=False,
                    platform="instagram_reels",
                    error="Resposta da Meta não continha container ID ou upload URI.",
                )

            # 2. Upload binário do vídeo via resumable upload
            file_size = path.stat().st_size
            video_bytes = path.read_bytes()

            upload_headers = {
                "Authorization": f"OAuth {self.access_token}",
                "offset": "0",
                "file_size": str(file_size),
            }

            resp_upload = self.session.post(
                upload_uri,
                headers=upload_headers,
                data=video_bytes,
                timeout=120,
            )
            if resp_upload.status_code not in (200, 201):
                err_msg = self._extract_error_message(resp_upload)
                return PublishResult(
                    success=False,
                    platform="instagram_reels",
                    error=f"Falha no upload dos bytes do vídeo: {err_msg}",
                )

            # 3. Polling de status do container
            status_url = f"{self.graph_base_url}/{container_id}"
            status_params = {
                "fields": "status_code,status",
                "access_token": self.access_token,
            }

            is_ready = False
            for _ in range(self.max_poll_attempts):
                resp_status = self.session.get(status_url, params=status_params, timeout=30)
                if resp_status.status_code == 200:
                    status_data = resp_status.json()
                    status_code = status_data.get("status_code", "").upper()

                    if status_code == "FINISHED":
                        is_ready = True
                        break
                    elif status_code == "ERROR":
                        error_detail = status_data.get("status", "Erro desconhecido no encode")
                        return PublishResult(
                            success=False,
                            platform="instagram_reels",
                            error=f"Falha no processamento do container Meta: {error_detail}",
                        )
                    elif status_code in ("IN_PROGRESS", "EXPIRED"):
                        if status_code == "EXPIRED":
                            return PublishResult(
                                success=False,
                                platform="instagram_reels",
                                error="Container expirou antes do término do encode.",
                            )

                time.sleep(self.poll_interval_seconds)

            if not is_ready:
                return PublishResult(
                    success=False,
                    platform="instagram_reels",
                    error=f"Timeout aguardando processamento do vídeo no Instagram após {self.max_poll_attempts} tentativas.",
                )

            # 4. Publicação definitiva
            publish_url = f"{self.graph_base_url}/{self.instagram_account_id}/media_publish"
            publish_payload = {
                "creation_id": container_id,
                "access_token": self.access_token,
            }

            resp_publish = self.session.post(publish_url, data=publish_payload, timeout=30)
            if resp_publish.status_code != 200:
                err_msg = self._extract_error_message(resp_publish)
                return PublishResult(
                    success=False,
                    platform="instagram_reels",
                    error=f"Falha ao publicar Reel: {err_msg}",
                )

            publish_data = resp_publish.json()
            media_id = publish_data.get("id")
            if not media_id:
                return PublishResult(
                    success=False,
                    platform="instagram_reels",
                    error="Resposta de publicação da Meta não retornou ID de mídia.",
                )

            url = f"https://instagram.com/reel/{media_id}"
            logger.info("Vídeo publicado com sucesso no Instagram Reels: %s", url)

            return PublishResult(
                success=True,
                platform="instagram_reels",
                post_id=media_id,
                url=url,
            )

        except Exception as e:
            err_msg = f"Exceção durante publicação no Instagram Reels: {e}"
            logger.error(err_msg)
            return PublishResult(
                success=False,
                platform="instagram_reels",
                error=err_msg,
            )
