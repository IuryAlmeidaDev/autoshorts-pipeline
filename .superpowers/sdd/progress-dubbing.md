# Dubbing & Translation Progress Ledger

Plan: `docs/superpowers/plans/2026-10-01-dubbing-translation.md`

## Status
- [x] Task 1: Suporte a Múltiplos Idiomas no Modelo e Banco de Dados
- [x] Task 2: Curador com Tradução e Adaptação de Roteiro para Português
- [x] Task 3: Sintetizador de Voz Neural com Edge-TTS
- [x] Task 4: Mixagem de Áudio com Ducking no Renderizador FFmpeg
- [x] Task 5: Roteamento de Episódios Internacionais no Orquestrador e CLI

## Task Log
### Task 1: Suporte a Múltiplos Idiomas no Modelo e Banco de Dados
- Adicionado campo `language: str = "pt"` no modelo `Channel` (`src/models.py`).
- Atualizado `init_db()` em `src/database.py` com coluna `language TEXT NOT NULL DEFAULT 'pt'` e migração idempotente com `PRAGMA table_info`.
- Atualizado `add_channel` para aceitar `language: str = "pt"`.
- Atualizado `get_active_channels` para aceitar filtro opcional `language: Optional[str] = None`.
- Adicionados testes de banco e migração em `tests/test_database.py`.
- Suíte completa de testes executada com sucesso (162 testes passando, zero regressões).

### Task 2: Curador com Tradução e Adaptação de Roteiro para Português
- Adicionados campos `translated_script: Optional[str] = None` e `voice_gender: str = "male"` no dataclass `ClipMetadata`.
- Atualizada função `parse_llm_clip_response` para extrair e normalizar `translated_script` e `voice_gender` (`male` ou `female`).
- Implementado método `analyze_and_translate_transcript` em `CuratorAnalyzer` com engenharia de prompt para garimpo de cortes, tradução coloquial/conversacional para português brasileiro, detecção de gênero e ganchos em português.
- Adicionados testes unitários completos em `tests/test_curator.py`.
- Suíte completa de testes executada com sucesso (169 testes passando, zero regressões).

### Task 3: Sintetizador de Voz Neural com Edge-TTS
- Criado pacote `src/dubbing` com exportações públicas em `__init__.py`.
- Criado módulo `src/dubbing/voice_synthesizer.py` implementando:
  - Constantes de vozes neurais brasileiras padrão (`pt-BR-AntonioNeural` e `pt-BR-FranciscaNeural`).
  - Exceção especializada `VoiceSynthesisError`.
  - Classe `VoiceSynthesizer` com seleção por gênero, validações robustas de texto, suporte a diretório temporário configurável.
  - Método `synthesize_async` utilizando `edge_tts.Communicate` com `boundary="WordBoundary"` para gravação do arquivo de áudio `.mp3` e extração precisa de `WordTimestamp` em segundos.
  - Método wrapper síncrono `synthesize` seguro contra event loops ativos.
- Criada suíte de testes unitários determinísticos em `tests/test_dubbing.py` com mocks de streaming assíncrono.
- Suíte completa de testes executada com sucesso (181 testes passando, zero regressões).

### Task 4: Mixagem de Áudio com Ducking no Renderizador FFmpeg
- Atualizado `build_filter_complex` em `src/editor/renderer.py` com suporte aos parâmetros `has_dubbing: bool = False` e `ducking_volume: float = 0.15`. Quando ativado, constrói os labels `[0:v]` e `[vout]` no grafo de vídeo e adiciona a cadeia de mixagem de áudio com atenuação ducking: `[0:a]volume={ducking_volume}[bg_audio];[1:a]volume=1.0[fg_audio];[bg_audio][fg_audio]amix=inputs=2:duration=first:dropout_transition=2[aout]`.
- Atualizado `build_ffmpeg_render_command` para aceitar `dubbing_audio: Optional[Union[Path, str]] = None`. Quando presente, insere o segundo input `-i`, define `-filter_complex` e mapeia `-map "[vout]" -map "[aout]"`. Em fluxos sem dublagem, mantém compatibilidade exata com `-vf`.
- Atualizado `VideoRenderer.render_clip` com suporte a `dubbing_audio` e `ducking_volume`, validando a existência do arquivo de dublagem via `FileNotFoundError`.
- Adicionados 8 novos testes em `tests/test_renderer.py` cobrindo smart crop com dublagem (volume padrão e customizado), blurred background com dublagem, combinação com gancho e legendas ASS, montagem de comando dual-audio e validação de arquivo inexistente.
- Suíte completa de testes executada com sucesso (189 testes passando, zero regressões).

### Task 5: Roteamento de Episódios Internacionais no Orquestrador e CLI
- Integrado `VoiceSynthesizer` em `PipelineOrchestrator` (`src/orchestrator.py`) com injeção de dependência e inicialização padrão.
- Adicionado método `get_channel(channel_id: str) -> Optional[Channel]` em `Database` (`src/database.py`).
- Implementado roteamento inteligente em `process_episode`:
  - Para canais com `language == "en"`: busca transcrição com `languages=["en", "en-US"]`, aciona `analyze_and_translate_transcript`, executa síntese neural de áudio via `VoiceSynthesizer`, renderiza o vídeo 9:16 com áudio de dublagem, ducking no áudio original (volume 0.15) e legendas dinâmicas perfeitamente sincronizadas, com limpeza automática do arquivo temporário de dublagem e fallback para legendas Whisper se não houver script traduzido.
  - Para canais nacionais (`language != "en"`): preserva intacto o fluxo original com legendas Whisper e sem áudio secundário.
- Atualizado comando CLI `add-channel` (`main.py`) com flags `--lang` e `--language` (default: `"pt"`, choices: `["pt", "en"]`).
- Adicionados 5 novos testes de orquestração e CLI em `tests/test_orchestrator.py`.
- Suíte completa de testes executada com 100% de sucesso (194 testes passando, zero regressões).
