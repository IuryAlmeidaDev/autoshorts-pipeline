# Task 9 Report: Orquestrador Geral e Dockerização

## Status
DONE

## Commit Hash
`8b74614`

## Arquivos Criados / Modificados
- `src/orchestrator.py`:
  - Classe `PipelineOrchestrator`:
    - Coordena o ciclo de vida completo do pipeline unificando `ScoutMonitor`, `TranscriptFetcher`, `CuratorAnalyzer`, `SurgicalDownloader`, `VideoRenderer` e publicadores (`YouTubeShortsPublisher`, `TikTokPublisher`, `InstagramReelsPublisher`, `KwaiPublisher`).
    - Método `process_episode(episode)`:
      - Obtém transcrição oficial ou gerada via `TranscriptFetcher`.
      - Identifica momentos virais com `CuratorAnalyzer` usando o modelo Gemini.
      - Para cada corte identificado: realiza download cirúrgico via `SurgicalDownloader`, extrai legendas palavra por palavra com Whisper, renderiza vídeo em 9:16 (1080x1920) com gancho visual e legendas estilizadas via `VideoRenderer`.
      - Salva o clipe no banco de dados (`db.save_clip`) e agenda as postagens pendentes para todas as plataformas de vídeo curto (`youtube_shorts`, `tiktok`, `instagram_reels`, `kwai`).
      - Marca o episódio como processado no banco de dados.
    - Método `run_scout_cycle()`:
      - Varre todos os canais ativos cadastrados e processa novos episódios não catalogados, retornando o total processado com tolerância a falhas por episódio.
    - Método `run_publishing_cycle()`:
      - Consulta postagens pendentes (`db.get_pending_posts()`) e publica na respectiva rede social.
      - Atualiza o status no banco de dados (`posted` ou `failed` com log de erro).
      - Remove arquivos de vídeo temporários em disco quando todas as postagens daquele clipe estiverem concluídas.
    - Método `setup_scheduler(blocking=False)`:
      - Configura os jobs periódicos `scout_cycle` e `publishing_cycle` com intervalos customizados via `APScheduler` (`BackgroundScheduler` ou `BlockingScheduler`).
- `src/database.py`:
  - Adicionados métodos auxiliares `get_clip(clip_id)` e `get_posts_for_clip(clip_id)` para consulta contextual de cortes e postagens.
- `main.py`:
  - Ponto de entrada CLI principal com suporte a comandos:
    - `python main.py run`: Inicia a execução contínua 24/7 com APScheduler e captura graciosa de encerramento (`SIGINT`/`KeyboardInterrupt`).
    - `python main.py add-channel <channel_id> <name>`: Cadastra ou reativa canal no banco de dados SQLite.
    - `python main.py once`: Executa uma única rodada imediata de scouting e publicação.
- `Dockerfile`:
  - Imagem Linux Python 3.11-slim configurada com `ffmpeg`, fontes TrueType (`fonts-dejavu-core`, `fonts-freefont-ttf`, `fonts-montserrat`), Playwright Chromium e dependências para execução headless.
  - Volumes declarados para `/app/storage` e `/app/secrets`.
- `docker-compose.yml`:
  - Definição do serviço `autoshorts` com mapeamento de volumes persistentes (`./storage`, `./secrets`), injeção de `.env`, `restart: unless-stopped` e inicialização padrão com `python main.py run`.
- `tests/test_orchestrator.py`:
  - Suíte com 17 testes unitários e de integração cobrindo:
    - Inicialização padrão e injeção de dependências customizadas.
    - Ciclo completo de processamento de episódio com persistência no banco e agendamento de posts para 4 plataformas.
    - Casos limítrofes: vídeo sem transcrição e transcrição sem momentos virais (ambos marcados defensivamente como processados).
    - Tolerância a falha na extração de legendas Whisper, executando renderização sem legendas sem abortar o fluxo.
    - Ciclo de scouting com processamento sequencial e isolamento de erros por episódio.
    - Ciclo de publicação com postagens bem-sucedidas, exclusão segura de arquivos após publicação completa e retenção de arquivos caso existam postagens pendentes.
    - Tratamento de erros de publicação e ausência de arquivo físico.
    - Configuração de jobs no `APScheduler` (`BackgroundScheduler` e `BlockingScheduler`).
    - Execução dos comandos CLI `add-channel`, `once` e `run` via `main.py`.

## Evidências dos Testes (TDD)

### 1. Falha Inicial (Red Phase)
```text
=================================== ERRORS ====================================
_________________ ERROR collecting tests/test_orchestrator.py _________________
ImportError while importing test module 'C:\Users\03573608183\autoshorts-pipeline\tests\test_orchestrator.py'.
Traceback:
tests\test_orchestrator.py:16: in <module>
    from src.orchestrator import PipelineOrchestrator
E   ModuleNotFoundError: No module named 'src.orchestrator'
=========================== short test summary info ===========================
ERROR tests/test_orchestrator.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
```

### 2. Aprovação dos Testes Unitários da Task 9 (Green Phase)
```text
tests/test_orchestrator.py::TestOrchestratorInit::test_default_initialization PASSED [  5%]
tests/test_orchestrator.py::TestOrchestratorInit::test_custom_dependency_injection PASSED [ 11%]
tests/test_orchestrator.py::TestProcessEpisode::test_process_episode_success PASSED [ 17%]
tests/test_orchestrator.py::TestProcessEpisode::test_process_episode_no_transcript PASSED [ 23%]
tests/test_orchestrator.py::TestProcessEpisode::test_process_episode_no_viral_moments_found PASSED [ 29%]
tests/test_orchestrator.py::TestProcessEpisode::test_process_episode_whisper_failure_fallback PASSED [ 35%]
tests/test_orchestrator.py::TestRunScoutCycle::test_run_scout_cycle_processes_multiple PASSED [ 41%]
tests/test_orchestrator.py::TestRunScoutCycle::test_run_scout_cycle_handles_episode_error_gracefully PASSED [ 47%]
tests/test_orchestrator.py::TestRunPublishingCycle::test_publishing_cycle_success_and_cleanup PASSED [ 52%]
tests/test_orchestrator.py::TestRunPublishingCycle::test_publishing_cycle_partial_posts_keeps_clip_file PASSED [ 58%]
tests/test_orchestrator.py::TestRunPublishingCycle::test_publishing_cycle_failure_records_error PASSED [ 64%]
tests/test_orchestrator.py::TestRunPublishingCycle::test_publishing_cycle_missing_video_file_fails PASSED [ 70%]
tests/test_orchestrator.py::TestScheduler::test_setup_scheduler_background PASSED [ 76%]
tests/test_orchestrator.py::TestScheduler::test_setup_scheduler_blocking PASSED [ 82%]
tests/test_orchestrator.py::TestCliMain::test_cli_add_channel PASSED     [ 88%]
tests/test_orchestrator.py::TestCliMain::test_cli_once PASSED            [ 94%]
tests/test_orchestrator.py::TestCliMain::test_cli_run PASSED             [100%]

============================= 17 passed in 1.28s ==============================
```

### 3. Regressão Zero na Suíte Completa
```text
============================= 160 passed in 3.52s =============================
```
160 testes aprovados em toda a base de código (Tasks 1 a 9).
