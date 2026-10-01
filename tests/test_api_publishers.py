"""Testes para o módulo de publicadores de API oficial (YouTube Shorts e Instagram Reels)."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from src.publisher.base import BasePublisher, PublishResult
from src.publisher.youtube import YouTubeShortsPublisher
from src.publisher.instagram import InstagramReelsPublisher
from src.publisher import (
    PublishResult as ExportedPublishResult,
    BasePublisher as ExportedBasePublisher,
    YouTubeShortsPublisher as ExportedYouTubePublisher,
    InstagramReelsPublisher as ExportedInstagramPublisher,
)


# ============================================================================
# Testes do Contrato Base e Utilitários (BasePublisher & PublishResult)
# ============================================================================

class TestBasePublisher:
    """Testes para a classe abstrata BasePublisher e dataclass PublishResult."""

    def test_publish_result_fields_and_defaults(self):
        """Verifica a estrutura e valores padrão de PublishResult."""
        res_success = PublishResult(
            success=True,
            platform="youtube_shorts",
            post_id="xyz123",
            url="https://youtube.com/shorts/xyz123",
        )
        assert res_success.success is True
        assert res_success.platform == "youtube_shorts"
        assert res_success.post_id == "xyz123"
        assert res_success.url == "https://youtube.com/shorts/xyz123"
        assert res_success.error is None

        res_failure = PublishResult(
            success=False,
            platform="instagram_reels",
            error="Token expired",
        )
        assert res_failure.success is False
        assert res_failure.platform == "instagram_reels"
        assert res_failure.post_id is None
        assert res_failure.url is None
        assert res_failure.error == "Token expired"

    def test_cannot_instantiate_abstract_base_publisher(self):
        """Verifica que BasePublisher não pode ser instanciada diretamente sem implementar publish."""
        with pytest.raises(TypeError):
            BasePublisher()

    def test_format_caption_title_only(self):
        """Testa formatação de legenda apenas com título."""
        class DummyPublisher(BasePublisher):
            def publish(self, video_path, title, description="", hashtags=None):
                return PublishResult(success=True, platform="dummy")

        pub = DummyPublisher()
        caption = pub.format_caption(title="Título Incrível")
        assert caption == "Título Incrível"

    def test_format_caption_title_and_description(self):
        """Testa formatação de legenda com título e descrição."""
        class DummyPublisher(BasePublisher):
            def publish(self, video_path, title, description="", hashtags=None):
                return PublishResult(success=True, platform="dummy")

        pub = DummyPublisher()
        caption = pub.format_caption(
            title="Dicas de Python",
            description="Aprenda neste vídeo curto como iterar melhor.",
        )
        assert caption == "Dicas de Python\n\nAprenda neste vídeo curto como iterar melhor."

    def test_format_caption_with_hashtags(self):
        """Testa inclusão e normalização de hashtags com e sem '#'."""
        class DummyPublisher(BasePublisher):
            def publish(self, video_path, title, description="", hashtags=None):
                return PublishResult(success=True, platform="dummy")

        pub = DummyPublisher()
        caption = pub.format_caption(
            title="Corte Viral",
            description="Assista até o fim!",
            hashtags=["python", "#coding", "viral", "#shorts"],
        )
        assert "Corte Viral" in caption
        assert "Assista até o fim!" in caption
        assert "#python #coding #viral #shorts" in caption

    def test_format_caption_strips_unnecessary_whitespace(self):
        """Testa limpeza de espaços e linhas extras na legenda."""
        class DummyPublisher(BasePublisher):
            def publish(self, video_path, title, description="", hashtags=None):
                return PublishResult(success=True, platform="dummy")

        pub = DummyPublisher()
        caption = pub.format_caption(
            title="  Título com Espaços  ",
            description="   ",
            hashtags=[],
        )
        assert caption == "Título com Espaços"


# ============================================================================
# Testes do Publicador do YouTube Shorts
# ============================================================================

class TestYouTubeShortsPublisher:
    """Testes unitários com mocks para o YouTubeShortsPublisher."""

    @pytest.fixture
    def dummy_video(self, tmp_path):
        video = tmp_path / "test_short.mp4"
        video.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 100)
        return video

    def test_init_defaults(self):
        """Verifica a inicialização padrão do publisher do YouTube."""
        pub = YouTubeShortsPublisher(privacy_status="unlisted")
        assert pub.privacy_status == "unlisted"
        assert pub.client_secrets_file is not None

    def test_file_not_found_returns_failure(self, tmp_path):
        """Verifica que arquivo de vídeo inexistente retorna erro seguro."""
        non_existent = tmp_path / "does_not_exist.mp4"
        pub = YouTubeShortsPublisher()
        result = pub.publish(video_path=non_existent, title="Meu Vídeo")
        assert result.success is False
        assert result.platform == "youtube_shorts"
        assert "não encontrado" in result.error.lower()

    def test_publish_ensures_shorts_hashtag_added_to_title(self, dummy_video):
        """Verifica que se #Shorts não constar no título nem na descrição, ele é incluído automaticamente."""
        mock_youtube_service = MagicMock()
        mock_insert = MagicMock()
        mock_youtube_service.videos.return_value.insert.return_value = mock_insert
        # Simula resposta do upload
        mock_insert.next_chunk.return_value = (None, {"id": "yt_video_123"})

        pub = YouTubeShortsPublisher(youtube_service=mock_youtube_service)

        with patch("src.publisher.youtube.MediaFileUpload") as mock_media:
            result = pub.publish(
                video_path=dummy_video,
                title="Meu Corte do Podcast",
                description="Confira este episódio",
                hashtags=["podcast", "cortes"],
            )

            assert result.success is True
            assert result.platform == "youtube_shorts"
            assert result.post_id == "yt_video_123"
            assert result.url == "https://youtube.com/shorts/yt_video_123"

            # Inserção chamada com body contendo #Shorts
            called_kwargs = mock_youtube_service.videos.return_value.insert.call_args[1]
            body = called_kwargs["body"]
            title_sent = body["snippet"]["title"]
            desc_sent = body["snippet"]["description"]
            assert "#Shorts" in title_sent or "#Shorts" in desc_sent or "#shorts" in desc_sent.lower()

    def test_publish_keeps_existing_shorts_hashtag(self, dummy_video):
        """Verifica que se #Shorts já estiver no título, não duplica desnecessariamente."""
        mock_youtube_service = MagicMock()
        mock_insert = MagicMock()
        mock_youtube_service.videos.return_value.insert.return_value = mock_insert
        mock_insert.next_chunk.return_value = (None, {"id": "yt_video_456"})

        pub = YouTubeShortsPublisher(youtube_service=mock_youtube_service)

        with patch("src.publisher.youtube.MediaFileUpload"):
            result = pub.publish(
                video_path=dummy_video,
                title="Melhor Momento #Shorts",
                description="Veja agora",
            )
            assert result.success is True
            body = mock_youtube_service.videos.return_value.insert.call_args[1]["body"]
            # Conta ocorrências de #shorts (case-insensitive) no título
            assert body["snippet"]["title"].lower().count("#shorts") == 1

    def test_publish_chunked_upload_loop(self, dummy_video):
        """Verifica o progresso de upload com múltiplos chunks via next_chunk."""
        mock_youtube_service = MagicMock()
        mock_insert = MagicMock()
        mock_youtube_service.videos.return_value.insert.return_value = mock_insert

        # Simula 2 chunks: chunk 1 em progresso (None), chunk 2 concluído
        mock_status = MagicMock()
        mock_status.progress.return_value = 0.5
        mock_insert.next_chunk.side_effect = [
            (mock_status, None),
            (mock_status, {"id": "chunked_id_789"}),
        ]

        pub = YouTubeShortsPublisher(youtube_service=mock_youtube_service)

        with patch("src.publisher.youtube.MediaFileUpload"):
            result = pub.publish(
                video_path=dummy_video,
                title="Vídeo com múltiplos chunks #Shorts",
            )
            assert result.success is True
            assert result.post_id == "chunked_id_789"
            assert mock_insert.next_chunk.call_count == 2

    def test_publish_api_http_error(self, dummy_video):
        """Verifica tratamento seguro quando a API do YouTube retorna HttpError (ex: cota excedida)."""
        from googleapiclient.errors import HttpError
        from httplib2 import Response

        mock_resp = Response({"status": 403, "reason": "quotaExceeded"})
        http_error = HttpError(resp=mock_resp, content=b'{"error": {"message": "The request cannot be completed because you have exceeded your quota."}}')

        mock_youtube_service = MagicMock()
        mock_youtube_service.videos.return_value.insert.side_effect = http_error

        pub = YouTubeShortsPublisher(youtube_service=mock_youtube_service)

        with patch("src.publisher.youtube.MediaFileUpload"):
            result = pub.publish(
                video_path=dummy_video,
                title="Vídeo Cota Excedida",
            )
            assert result.success is False
            assert result.platform == "youtube_shorts"
            assert "quota" in result.error.lower() or "403" in result.error

    def test_publish_auth_error_when_service_cannot_be_built(self, dummy_video):
        """Verifica que se o serviço não puder ser autenticado, retorna PublishResult de falha."""
        pub = YouTubeShortsPublisher(client_secrets_file="non_existent_secret.json")

        result = pub.publish(
            video_path=dummy_video,
            title="Vídeo Sem Auth",
        )
        assert result.success is False
        assert result.platform == "youtube_shorts"
        assert "client_secrets" in result.error.lower() or "não encontrado" in result.error.lower()


# ============================================================================
# Testes do Publicador do Instagram Reels
# ============================================================================

class TestInstagramReelsPublisher:
    """Testes unitários com mocks para o InstagramReelsPublisher via Meta Graph API."""

    @pytest.fixture
    def dummy_video(self, tmp_path):
        video = tmp_path / "test_reel.mp4"
        video.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 200)
        return video

    def test_init_defaults(self):
        """Verifica inicialização padrão do InstagramReelsPublisher."""
        pub = InstagramReelsPublisher(access_token="tok_123", instagram_account_id="act_456")
        assert pub.access_token == "tok_123"
        assert pub.instagram_account_id == "act_456"
        assert pub.api_version == "v19.0"

    def test_missing_credentials_returns_failure(self, dummy_video):
        """Verifica que falta de access token ou account id resulta em falha clara."""
        pub = InstagramReelsPublisher(access_token="", instagram_account_id="")
        result = pub.publish(video_path=dummy_video, title="Reel sem credenciais")
        assert result.success is False
        assert result.platform == "instagram_reels"
        assert "credencia" in result.error.lower() or "token" in result.error.lower()

    def test_file_not_found_returns_failure(self, tmp_path):
        """Verifica que vídeo inexistente retorna erro seguro."""
        non_existent = tmp_path / "non_existent_reel.mp4"
        pub = InstagramReelsPublisher(access_token="tok", instagram_account_id="act")
        result = pub.publish(video_path=non_existent, title="Reel Inexistente")
        assert result.success is False
        assert result.platform == "instagram_reels"
        assert "não encontrado" in result.error.lower()

    def test_full_pipeline_success(self, dummy_video):
        """Testa o fluxo completo de 4 etapas:
        1. Criação do container de mídia (POST /{ig_user_id}/media)
        2. Upload resumable de bytes (POST {upload_uri})
        3. Polling de status até FINISHED (GET /{container_id})
        4. Publicação definitiva (POST /{ig_user_id}/media_publish)
        """
        mock_session = MagicMock()

        # Step 1: Container creation
        res_container = MagicMock()
        res_container.status_code = 200
        res_container.json.return_value = {
            "id": "container_111",
            "uri": "https://rupload.facebook.com/reel-upload/container_111",
        }

        # Step 2: Resumable binary upload
        res_upload = MagicMock()
        res_upload.status_code = 200
        res_upload.json.return_value = {"success": True}

        # Step 3: Status polling (primeiro IN_PROGRESS, depois FINISHED)
        res_poll_1 = MagicMock()
        res_poll_1.status_code = 200
        res_poll_1.json.return_value = {"status_code": "IN_PROGRESS", "id": "container_111"}

        res_poll_2 = MagicMock()
        res_poll_2.status_code = 200
        res_poll_2.json.return_value = {"status_code": "FINISHED", "id": "container_111"}

        # Step 4: Publish
        res_publish = MagicMock()
        res_publish.status_code = 200
        res_publish.json.return_value = {"id": "reel_media_999"}

        # Configura as chamadas em ordem
        mock_session.post.side_effect = [res_container, res_upload, res_publish]
        mock_session.get.side_effect = [res_poll_1, res_poll_2]

        pub = InstagramReelsPublisher(
            access_token="valid_token",
            instagram_account_id="ig_account_123",
            session=mock_session,
            poll_interval_seconds=0.01,
        )

        result = pub.publish(
            video_path=dummy_video,
            title="Corte Incrível de IA",
            description="Veja como a tecnologia evoluiu.",
            hashtags=["ia", "tech", "reels"],
        )

        assert result.success is True
        assert result.platform == "instagram_reels"
        assert result.post_id == "reel_media_999"
        assert result.url == "https://instagram.com/reel/reel_media_999"

        # Verifica chamadas
        assert mock_session.post.call_count == 3
        assert mock_session.get.call_count == 2

    def test_container_creation_http_error(self, dummy_video):
        """Verifica falha se a criação do container retornar erro da Meta Graph API."""
        mock_session = MagicMock()
        res_error = MagicMock()
        res_error.status_code = 400
        res_error.json.return_value = {
            "error": {
                "message": "Invalid OAuth access token.",
                "type": "OAuthException",
                "code": 190,
            }
        }
        res_error.raise_for_status.side_effect = Exception("400 Client Error: Bad Request")
        mock_session.post.return_value = res_error

        pub = InstagramReelsPublisher(
            access_token="bad_token",
            instagram_account_id="ig_account_123",
            session=mock_session,
        )

        result = pub.publish(video_path=dummy_video, title="Reel com Erro")
        assert result.success is False
        assert result.platform == "instagram_reels"
        assert "Invalid OAuth access token" in result.error or "400" in result.error

    def test_container_processing_status_error(self, dummy_video):
        """Verifica falha quando o container vai para status ERROR (falha de encode da Meta)."""
        mock_session = MagicMock()

        res_container = MagicMock()
        res_container.status_code = 200
        res_container.json.return_value = {"id": "container_err", "uri": "https://upload.url"}

        res_upload = MagicMock()
        res_upload.status_code = 200
        res_upload.json.return_value = {"success": True}

        res_poll_err = MagicMock()
        res_poll_err.status_code = 200
        res_poll_err.json.return_value = {
            "status_code": "ERROR",
            "status": "Transcode failed: unsupported codec",
        }

        mock_session.post.side_effect = [res_container, res_upload]
        mock_session.get.return_value = res_poll_err

        pub = InstagramReelsPublisher(
            access_token="valid_token",
            instagram_account_id="ig_account_123",
            session=mock_session,
            poll_interval_seconds=0.01,
        )

        result = pub.publish(video_path=dummy_video, title="Reel Codec Inválido")
        assert result.success is False
        assert result.platform == "instagram_reels"
        assert "Transcode failed" in result.error or "ERROR" in result.error

    def test_container_processing_timeout(self, dummy_video):
        """Verifica que exceder o número máximo de tentativas de polling encerra com erro de timeout."""
        mock_session = MagicMock()

        res_container = MagicMock()
        res_container.status_code = 200
        res_container.json.return_value = {"id": "container_slow", "uri": "https://upload.url"}

        res_upload = MagicMock()
        res_upload.status_code = 200
        res_upload.json.return_value = {"success": True}

        res_poll_progress = MagicMock()
        res_poll_progress.status_code = 200
        res_poll_progress.json.return_value = {"status_code": "IN_PROGRESS"}

        mock_session.post.side_effect = [res_container, res_upload]
        mock_session.get.return_value = res_poll_progress

        pub = InstagramReelsPublisher(
            access_token="valid_token",
            instagram_account_id="ig_account_123",
            session=mock_session,
            poll_interval_seconds=0.01,
            max_poll_attempts=3,
        )

        result = pub.publish(video_path=dummy_video, title="Reel Timeout")
        assert result.success is False
        assert result.platform == "instagram_reels"
        assert "timeout" in result.error.lower() or "limite" in result.error.lower()

    def test_publish_step_http_error(self, dummy_video):
        """Verifica falha se a chamada final de media_publish falhar."""
        mock_session = MagicMock()

        res_container = MagicMock()
        res_container.status_code = 200
        res_container.json.return_value = {"id": "container_ok", "uri": "https://upload.url"}

        res_upload = MagicMock()
        res_upload.status_code = 200
        res_upload.json.return_value = {"success": True}

        res_poll_ok = MagicMock()
        res_poll_ok.status_code = 200
        res_poll_ok.json.return_value = {"status_code": "FINISHED"}

        res_pub_err = MagicMock()
        res_pub_err.status_code = 500
        res_pub_err.json.return_value = {"error": {"message": "Internal Server Error"}}
        res_pub_err.raise_for_status.side_effect = Exception("500 Server Error")

        mock_session.post.side_effect = [res_container, res_upload, res_pub_err]
        mock_session.get.return_value = res_poll_ok

        pub = InstagramReelsPublisher(
            access_token="valid_token",
            instagram_account_id="ig_account_123",
            session=mock_session,
            poll_interval_seconds=0.01,
        )

        result = pub.publish(video_path=dummy_video, title="Reel Falha Publish")
        assert result.success is False
        assert result.platform == "instagram_reels"
        assert "500" in result.error or "Internal Server Error" in result.error


# ============================================================================
# Testes de Exportação do Pacote
# ============================================================================

def test_package_exports():
    """Garante que o pacote src.publisher exporta as classes públicas esperadas."""
    assert ExportedPublishResult is PublishResult
    assert ExportedBasePublisher is BasePublisher
    assert ExportedYouTubePublisher is YouTubeShortsPublisher
    assert ExportedInstagramPublisher is InstagramReelsPublisher
