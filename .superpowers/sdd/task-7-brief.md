# Task 7 Brief: Publicadores de API Oficial (YouTube Shorts & Instagram Reels)

## Objetivos
Construir o módulo de publicação através das APIs oficiais do YouTube (YouTube Data API v3) e Instagram (Meta Graph API Reels Publishing), com contrato unificado e tratamento de erros.

## Arquivos a criar
1. `src/publisher/__init__.py`
2. `src/publisher/base.py`
3. `src/publisher/youtube.py`
4. `src/publisher/instagram.py`
5. `tests/test_api_publishers.py`

## Especificações Técnicas

### 1. `src/publisher/base.py`
- Dataclass `PublishResult`:
  - `success: bool`
  - `platform: str`
  - `post_id: str | None = None`
  - `url: str | None = None`
  - `error: str | None = None`
- Classe abstrata `BasePublisher(ABC)`:
  - `@abstractmethod def publish(self, video_path: Path | str, title: str, description: str = "", hashtags: list[str] = None) -> PublishResult`
  - Método utilitário `format_caption(title: str, description: str = "", hashtags: list[str] = None) -> str`

### 2. `src/publisher/youtube.py`
- Classe `YouTubeShortsPublisher(BasePublisher)`:
  - `__init__(self, client_secrets_file: str | Path = None, credentials_file: str | Path = None, privacy_status: str = "public")`
  - Garante que a hashtag `#Shorts` esteja no título ou na descrição (essencial para categorização no YouTube Shorts).
  - Realiza upload em chunks usando `googleapiclient.http.MediaFileUpload`.
  - Retorna `PublishResult(success=True, platform='youtube_shorts', post_id=video_id, url=f"https://youtube.com/shorts/{video_id}")`.
  - Tratamento de exceções (erro de quota, autenticação, arquivo inexistente).

### 3. `src/publisher/instagram.py`
- Classe `InstagramReelsPublisher(BasePublisher)`:
  - `__init__(self, access_token: str = "", instagram_account_id: str = "", api_version: str = "v19.0")`
  - Implementa o fluxo oficial de Reels da Graph API:
    1. Criar container de mídia (`POST /{account_id}/media` com `media_type=REELS`, `caption=...`).
    2. Upload dos bytes do vídeo via upload resumable de sessão.
    3. Polling de status do container até status `FINISHED`.
    4. Publicação definitiva (`POST /{account_id}/media_publish`).
  - Retorna `PublishResult(success=True, platform='instagram_reels', post_id=media_id, url=f"https://instagram.com/reel/{media_id}")`.
  - Tratamento de tokens inválidos, limites de API e falhas de encode da Meta.

## Testes (`tests/test_api_publishers.py`)
- Testar `PublishResult` e formatação de legenda em `BasePublisher`.
- Testar `YouTubeShortsPublisher` com mock do cliente Google API (`discovery.build`) validando inserção de `#Shorts`, upload e retorno de URL.
- Testar `InstagramReelsPublisher` com mock das chamadas HTTP da Meta Graph API validando ciclo container -> upload -> publish.
- Testar tratamento de erro e preenchimento de `PublishResult(success=False, error=...)`.

## Critérios de Aceite
- Executar `pytest tests/test_api_publishers.py -v` com 100% de sucesso.
- Executar toda a suíte `pytest tests/` garantindo zero regressões.
- Git commit: `feat: official api publishers for youtube shorts and instagram reels`.
