# Task 9 Brief: Orquestrador Geral e Dockerização

## Objetivos
Unificar todos os módulos do pipeline no `PipelineOrchestrator`, criar o ponto de entrada principal (`main.py`) com agendador contínuo (`APScheduler`), e fornecer a infraestrutura Docker (`Dockerfile` e `docker-compose.yml`) com FFmpeg, fontes e Playwright pré-configurados para rodar 24/7 na VPS Linux.

## Arquivos a criar
1. `src/orchestrator.py`
2. `main.py`
3. `Dockerfile`
4. `docker-compose.yml`
5. `tests/test_orchestrator.py`

## Especificações Técnicas

### 1. `src/orchestrator.py`
- Classe `PipelineOrchestrator`:
  - `__init__(self, settings: Settings, db: Database, publishers: dict[str, BasePublisher] = None)`
  - Dependências internas: `ScoutMonitor`, `TranscriptFetcher`, `CuratorAnalyzer`, `SurgicalDownloader`, `VideoRenderer`.
  - Métodos principais:
    - `process_episode(episode: Episode) -> list[Clip]`:
      - Busca a transcrição do vídeo via `TranscriptFetcher`.
      - Analisa com `CuratorAnalyzer` e obtém os clipes virais.
      - Para cada clipe:
        - Executa o download cirúrgico com `SurgicalDownloader`.
        - Gera legendas dinâmicas com Whisper / timestamps.
        - Renderiza o corte 9:16 com gancho no topo via `VideoRenderer`.
        - Salva o clipe no banco (`db.save_clip`) e agenda as postagens (`db.create_post(clip.id, platform)` para YouTube Shorts, TikTok, Instagram Reels, Kwai).
      - Marca o episódio como processado no banco (`db.mark_video_processed`).
    - `run_scout_cycle() -> int`:
      - Varre canais cadastrados e processa novos episódios.
    - `run_publishing_cycle() -> int`:
      - Consulta `db.get_pending_posts()`.
      - Executa a postagem na plataforma designada.
      - Atualiza status no banco e remove arquivos temporários quando todas as postagens daquele clipe estiverem concluídas.
    - `setup_scheduler() -> BackgroundScheduler | BlockingScheduler`:
      - Configura os intervalos de execução periódica com `APScheduler`.

### 2. `main.py`
- Ponto de entrada CLI:
  - Inicializa banco, configurações e instâncias dos publicadores.
  - Suporta comandos:
    - `python main.py run`: Inicia o loop contínuo 24/7 com APScheduler.
    - `python main.py add-channel <id> <name>`: Cadastra canal para monitorar.
    - `python main.py once`: Executa uma única rodada imediata (scout + publish) para teste manual.

### 3. `Dockerfile` e `docker-compose.yml`
- Imagem Linux Python 3.11 com `ffmpeg`, fontes TrueType (FreeFont / DejaVu / Montserrat), dependências do Playwright Chromium.
- Instalação limpa via `pip install -r requirements.txt`.
- Execução de `playwright install --with-deps chromium`.
- Volumes montados para persistência em disco: `./storage` (banco de dados SQLite e vídeos) e `./secrets` (tokens e cookies).

## Testes (`tests/test_orchestrator.py`)
- Testar `PipelineOrchestrator.process_episode` mockando os serviços externos (transcrição, LLM, download, render) e validando transações de banco (clipe criado, posts pendentes gerados).
- Testar `run_publishing_cycle` com mocks dos publicadores validando transição de status para `posted` e remoção de arquivo temporário.
- Testar `setup_scheduler` validando agendamento dos jobs periódicos.

## Critérios de Aceite
- Executar `pytest tests/test_orchestrator.py -v` com 100% de sucesso.
- Executar toda a suíte `pytest tests/` garantindo zero regressões.
- Git commit: `feat: complete pipeline orchestrator and dockerization`.
