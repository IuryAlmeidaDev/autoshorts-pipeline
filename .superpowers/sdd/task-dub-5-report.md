# Task Dub-5 Report: Roteamento de Episódios Internacionais no Orquestrador e CLI

## Status
DONE

## Arquivos Criados / Modificados
- `src/orchestrator.py`:
  - Importação de `VoiceSynthesizer` de `src.dubbing`.
  - Suporte à injeção de dependência `voice_synthesizer: Optional[VoiceSynthesizer] = None` com default para `VoiceSynthesizer(temp_dir=self.settings.TEMP_DIR)`.
  - No método `process_episode`:
    - Consulta ao banco para identificação do canal e seu atributo `language`.
    - Roteamento condicional para canais com `language == "en"`:
      - Extração de transcrição prioritariamente em inglês (`languages=["en", "en-US"]`).
      - Chamada a `analyze_and_translate_transcript` no curador.
      - Para cada corte com `translated_script`: geração de áudio neural em português e timestamps com `voice_synthesizer.synthesize`, renderização com `dubbing_audio`, `ducking_volume=0.15` e legendas ASS sincronizadas, e remoção imediata do áudio temporário gerado.
      - Fallback suave para transcrição/legendas Whisper quando não houver `translated_script`.
    - Preservação intacta do fluxo nacional para canais com `language != "en"` (ou sem canal cadastrado).
- `src/database.py`:
  - Adicionado método `get_channel(channel_id: str) -> Optional[Channel]` permitindo busca direta de canal pelo identificador string do YouTube.
- `main.py`:
  - Adicionadas flags `--lang` e `--language` ao subcomando `add-channel` (com `default="pt"` e `choices=["pt", "en"]`).
  - Atualizada a função `cmd_add_channel` para propagar o idioma informado ao cadastrar o canal via `db.add_channel`.
- `tests/test_orchestrator.py`:
  - Testes de injeção padrão e customizada de `VoiceSynthesizer` no `PipelineOrchestrator`.
  - Teste do fluxo completo de dublagem para canais com `language="en"`, verificando busca de legendas em inglês, chamada a `analyze_and_translate_transcript`, síntese com voz apropriada ao gênero, renderização com ducking e áudio de dublagem, e deleção do áudio temporário.
  - Teste de fallback quando clipe internacional não possui `translated_script`.
  - Teste de preservação do fluxo nacional quando canal possui `language="pt"`.
  - Testes do CLI `add-channel` com `--lang en`, `--language en` e idioma padrão `"pt"`.

## Evidências dos Testes (TDD)

### 1. Falha Inicial (Red)
```text
FAILED tests/test_orchestrator.py::TestOrchestratorInit::test_default_initialization - AttributeError: 'PipelineOrchestrator' object has no attribute 'voice_synthesizer'
FAILED tests/test_orchestrator.py::TestOrchestratorInit::test_custom_dependency_injection - TypeError: PipelineOrchestrator.__init__() got an unexpected keyword argument 'voice_synthesizer'
FAILED tests/test_orchestrator.py::TestProcessEpisode::test_process_episode_international_channel_with_dubbing - TypeError: PipelineOrchestrator.__init__() got an unexpected keyword argument 'voice_synthesizer'
FAILED tests/test_orchestrator.py::TestProcessEpisode::test_process_episode_international_channel_fallback_no_script - TypeError: PipelineOrchestrator.__init__() got an unexpected keyword argument 'voice_synthesizer'
FAILED tests/test_orchestrator.py::TestProcessEpisode::test_process_episode_national_channel_standard_flow - TypeError: PipelineOrchestrator.__init__() got an unexpected keyword argument 'voice_synthesizer'
FAILED tests/test_orchestrator.py::TestCliMain::test_cli_add_channel_with_lang_en - SystemExit: 2
FAILED tests/test_orchestrator.py::TestCliMain::test_cli_add_channel_with_language_flag - SystemExit: 2
======================== 7 failed, 15 passed in 31.36s ========================
```

### 2. Aprovação dos Testes do Orquestrador e CLI (Green)
```text
============================= test session starts =============================
platform win32 -- Python 3.13.14, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\03573608183\autoshorts-pipeline
configfile: pyproject.toml
collected 22 items

tests/test_orchestrator.py::TestOrchestratorInit::test_default_initialization PASSED [  4%]
tests/test_orchestrator.py::TestOrchestratorInit::test_custom_dependency_injection PASSED [  9%]
tests/test_orchestrator.py::TestProcessEpisode::test_process_episode_success PASSED [ 13%]
tests/test_orchestrator.py::TestProcessEpisode::test_process_episode_no_transcript PASSED [ 18%]
tests/test_orchestrator.py::TestProcessEpisode::test_process_episode_no_viral_moments_found PASSED [ 22%]
tests/test_orchestrator.py::TestProcessEpisode::test_process_episode_whisper_failure_fallback PASSED [ 27%]
tests/test_orchestrator.py::TestProcessEpisode::test_process_episode_international_channel_with_dubbing PASSED [ 31%]
tests/test_orchestrator.py::TestProcessEpisode::test_process_episode_international_channel_fallback_no_script PASSED [ 36%]
tests/test_orchestrator.py::TestProcessEpisode::test_process_episode_national_channel_standard_flow PASSED [ 40%]
tests/test_orchestrator.py::TestRunScoutCycle::test_run_scout_cycle_processes_multiple PASSED [ 45%]
tests/test_orchestrator.py::TestRunScoutCycle::test_run_scout_cycle_handles_episode_error_gracefully PASSED [ 50%]
tests/test_orchestrator.py::TestRunPublishingCycle::test_publishing_cycle_success_and_cleanup PASSED [ 54%]
tests/test_orchestrator.py::TestRunPublishingCycle::test_publishing_cycle_partial_posts_keeps_clip_file PASSED [ 59%]
tests/test_orchestrator.py::TestRunPublishingCycle::test_publishing_cycle_failure_records_error PASSED [ 63%]
tests/test_orchestrator.py::TestRunPublishingCycle::test_publishing_cycle_missing_video_file_fails PASSED [ 68%]
tests/test_orchestrator.py::TestScheduler::test_setup_scheduler_background PASSED [ 72%]
tests/test_orchestrator.py::TestScheduler::test_setup_scheduler_blocking PASSED [ 77%]
tests/test_orchestrator.py::TestCliMain::test_cli_add_channel PASSED     [ 81%]
tests/test_orchestrator.py::TestCliMain::test_cli_add_channel_with_lang_en PASSED [ 86%]
tests/test_orchestrator.py::TestCliMain::test_cli_add_channel_with_language_flag PASSED [ 90%]
tests/test_orchestrator.py::TestCliMain::test_cli_once PASSED            [ 95%]
tests/test_orchestrator.py::TestCliMain::test_cli_run PASSED             [100%]

============================= 22 passed in 53.16s =============================
```

### 3. Regressão Zero na Suíte Completa
```text
======================= 194 passed in 90.71s (0:01:30) ========================
```
