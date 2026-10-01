# Task 2 Brief: Banco de Dados e Modelagem de Estados

## Objetivos
Implementar a camada de persistência com SQLite usando SQLAlchemy / SQLite padrão em `src/models.py` e `src/database.py`.

## Modelos (`src/models.py`)
1. `Channel`:
   - `id`: int (PK autoincrement)
   - `channel_id`: str (ID do canal no YouTube, ex: UC...)
   - `name`: str
   - `active`: bool (default True)
   - `created_at`: datetime

2. `Video`:
   - `id`: int (PK)
   - `channel_id`: str (FK para Channel.channel_id ou string)
   - `youtube_id`: str (Unique)
   - `title`: str
   - `processed_at`: datetime

3. `Clip`:
   - `id`: int (PK)
   - `video_id`: int (FK Video.id)
   - `start_time`: float
   - `end_time`: float
   - `hook_title`: str
   - `viral_score`: float
   - `file_path`: str (nullable)
   - `status`: str (ex: 'pending_render', 'rendered', 'published', 'failed')
   - `created_at`: datetime

4. `Post`:
   - `id`: int (PK)
   - `clip_id`: int (FK Clip.id)
   - `platform`: str ('youtube_shorts', 'tiktok', 'instagram_reels', 'kwai')
   - `status`: str ('pending', 'posted', 'failed')
   - `external_post_id`: str (nullable)
   - `error_log`: str (nullable)
   - `posted_at`: datetime (nullable)

## Repositório (`src/database.py`)
Classe `Database`:
- `__init__(self, db_path: Path | str)`
- `init_db()`: cria tabelas se não existirem
- `add_channel(channel_id: str, name: str) -> Channel`
- `get_active_channels() -> list[Channel]`
- `is_video_processed(youtube_id: str) -> bool`
- `mark_video_processed(youtube_id: str, channel_id: str, title: str) -> Video`
- `save_clip(video_id: int, start_time: float, end_time: float, hook_title: str, viral_score: float, file_path: str = None) -> Clip`
- `create_post(clip_id: int, platform: str) -> Post`
- `get_pending_posts(platform: str = None) -> list[Post]`
- `update_post_status(post_id: int, status: str, external_post_id: str = None, error_log: str = None)`

## Testes (`tests/test_database.py`)
- Testar criação do banco em arquivo temporário (`tmp_path`)
- Testar inserção e listagem de canais
- Testar verificação e marcação de vídeos processados
- Testar criação de clipes e fluxo de status de postagens

## Critérios de Aceite
- `python -m pytest tests/test_database.py` passando 100%.
- Git commit: `feat: database schema and state management implementation`.
