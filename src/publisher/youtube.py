"""Módulo de publicação no YouTube Shorts utilizando a YouTube Data API v3."""

import logging
from pathlib import Path
from typing import List, Optional, Union

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

from src.config import settings
from src.publisher.base import BasePublisher, PublishResult

logger = logging.getLogger(__name__)


class YouTubeShortsPublisher(BasePublisher):
    """Publicador para YouTube Shorts via YouTube Data API v3."""

    def __init__(
        self,
        client_secrets_file: Optional[Union[str, Path]] = None,
        credentials_file: Optional[Union[str, Path]] = None,
        privacy_status: str = "public",
        youtube_service=None,
    ):
        """Inicializa o publicador do YouTube Shorts.

        Args:
            client_secrets_file: Caminho para o client_secrets.json do OAuth2.
            credentials_file: Caminho para o token salvo de credenciais (ex: token.json).
            privacy_status: Status de visibilidade ('public', 'unlisted', 'private').
            youtube_service: Instância opcional pré-construída da API do YouTube (para testes ou DI).
        """
        self.client_secrets_file = Path(
            client_secrets_file or settings.YOUTUBE_CLIENT_SECRETS
        )
        self.credentials_file = Path(
            credentials_file or (settings.BASE_DIR / "secrets" / "youtube_token.json")
        )
        self.privacy_status = privacy_status
        self._youtube_service = youtube_service

    def _get_authenticated_service(self):
        """Obtém ou instancia o serviço autenticado da YouTube Data API v3."""
        if self._youtube_service is not None:
            return self._youtube_service

        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow

        scopes = ["https://www.googleapis.com/auth/youtube.upload"]
        credentials = None

        if self.credentials_file.exists():
            try:
                credentials = Credentials.from_authorized_user_file(
                    str(self.credentials_file), scopes=scopes
                )
            except Exception as e:
                logger.warning("Falha ao carregar credentials_file: %s", e)

        # Atualiza automaticamente o token expirado se houver refresh_token disponível
        if credentials and credentials.expired and credentials.refresh_token:
            try:
                from google.auth.transport.requests import Request
                credentials.refresh(Request())
                self.credentials_file.parent.mkdir(parents=True, exist_ok=True)
                self.credentials_file.write_text(credentials.to_json(), encoding="utf-8")
                logger.info("Token OAuth do YouTube atualizado com sucesso via refresh_token.")
            except Exception as e:
                logger.warning("Falha ao atualizar token do YouTube via refresh_token: %s", e)

        if not credentials or not credentials.valid:
            if not self.client_secrets_file.exists():
                raise FileNotFoundError(
                    f"client_secrets file não encontrado: {self.client_secrets_file}"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(self.client_secrets_file), scopes=scopes
            )
            try:
                credentials = flow.run_local_server(port=8080)
            except Exception:
                credentials = flow.run_local_server(port=0)
            self.credentials_file.parent.mkdir(parents=True, exist_ok=True)
            self.credentials_file.write_text(credentials.to_json(), encoding="utf-8")

        return build("youtube", "v3", credentials=credentials, cache_discovery=False)

    def publish(
        self,
        video_path: Union[Path, str],
        title: str,
        description: str = "",
        hashtags: Optional[List[str]] = None,
    ) -> PublishResult:
        """Envia um vídeo curto para o YouTube Shorts via upload em chunks.

        Garante a inclusão de #Shorts para categorização automática.
        """
        path = Path(video_path)
        if not path.is_file():
            return PublishResult(
                success=False,
                platform="youtube_shorts",
                error=f"Arquivo de vídeo não encontrado: {video_path}",
            )

        # Garante a hashtag #Shorts
        final_title = (title or "").strip()
        final_description = (description or "").strip()

        has_shorts = "#shorts" in final_title.lower() or "#shorts" in final_description.lower()
        if not has_shorts:
            if len(final_title) + len(" #Shorts") <= 100:
                final_title = f"{final_title} #Shorts".strip()
            else:
                final_description = f"{final_description}\n\n#Shorts".strip()

        # Monta tags da API
        tags = ["Shorts"]
        if hashtags:
            for tag in hashtags:
                clean_tag = tag.lstrip("#").strip()
                if clean_tag and clean_tag.lower() not in [t.lower() for t in tags]:
                    tags.append(clean_tag)

        try:
            service = self._get_authenticated_service()

            media = MediaFileUpload(
                str(path),
                mimetype="video/mp4",
                chunksize=1024 * 1024 * 4,  # 4 MB chunks
                resumable=True,
            )

            body = {
                "snippet": {
                    "title": final_title,
                    "description": final_description,
                    "tags": tags,
                    "categoryId": "22",  # People & Blogs
                },
                "status": {
                    "privacyStatus": self.privacy_status,
                    "selfDeclaredMadeForKids": False,
                },
            }

            insert_request = service.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media,
            )

            response = None
            while response is None:
                status, response = insert_request.next_chunk()
                if status:
                    logger.debug(
                        "Upload YouTube Shorts em andamento: %d%%",
                        int(status.progress() * 100),
                    )

            video_id = response.get("id")
            if not video_id:
                return PublishResult(
                    success=False,
                    platform="youtube_shorts",
                    error="API do YouTube não retornou ID de vídeo na resposta.",
                )

            url = f"https://youtube.com/shorts/{video_id}"
            logger.info("Vídeo publicado com sucesso no YouTube Shorts: %s", url)

            return PublishResult(
                success=True,
                platform="youtube_shorts",
                post_id=video_id,
                url=url,
            )

        except HttpError as e:
            error_msg = f"YouTube API HttpError {e.resp.status}: {e.content.decode('utf-8', errors='ignore') if hasattr(e, 'content') and e.content else str(e)}"
            logger.error(error_msg)
            return PublishResult(
                success=False,
                platform="youtube_shorts",
                error=error_msg,
            )
        except Exception as e:
            error_msg = f"Erro na publicação do YouTube Shorts: {e}"
            logger.error(error_msg)
            return PublishResult(
                success=False,
                platform="youtube_shorts",
                error=error_msg,
            )
