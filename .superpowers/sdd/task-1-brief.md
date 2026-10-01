# Task 1 Brief: Scaffolding, Estrutura Base e Configurações

## Objetivos
Criar a base do projeto em `C:/Users/03573608183/autoshorts-pipeline` com configurações tipadas, dependências e estrutura de pastas.

## Arquivos a criar
1. `pyproject.toml` - Definições de projeto Python 3.11 e ferramentas (pytest).
2. `requirements.txt` - Dependências essenciais:
   - `feedparser>=6.0.0`
   - `youtube-transcript-api>=0.6.0`
   - `google-genai>=0.1.0`
   - `yt-dlp>=2024.0.0`
   - `faster-whisper>=1.0.0`
   - `ffmpeg-python>=0.2.0`
   - `opencv-python>=4.8.0`
   - `mediapipe>=0.10.0`
   - `google-api-python-client>=2.0.0`
   - `google-auth-oauthlib>=1.0.0`
   - `playwright>=1.40.0`
   - `apscheduler>=3.10.0`
   - `pydantic>=2.0.0`
   - `pydantic-settings>=2.0.0`
   - `pytest>=7.0.0`
3. `.env.example` - Template de variáveis com valores padrão:
   - `POLL_INTERVAL_MINUTES=60`
   - `POST_INTERVAL_HOURS=4`
   - `MAX_CLIPS_PER_VIDEO=3`
   - `MIN_CLIP_DURATION=45`
   - `MAX_CLIP_DURATION=90`
   - `GEMINI_API_KEY=`
   - `YOUTUBE_CLIENT_SECRETS=secrets/youtube_client.json`
   - `INSTAGRAM_ACCESS_TOKEN=`
   - `INSTAGRAM_ACCOUNT_ID=`
4. `src/__init__.py`
5. `src/config.py` - Implementar classe `Settings` carregando de variáveis de ambiente com defaults seguros e diretórios `storage/temp`, `storage/output`, `storage/pipeline.db`.
6. `tests/__init__.py`
7. `tests/test_config.py` - Testar inicialização de `Settings` e criação correta de caminhos.

## Critérios de Aceite
- Executar `pytest tests/test_config.py` e passar com 100% de sucesso.
- Fazer commit no git com mensagem `feat: initial project scaffolding and configuration`.
