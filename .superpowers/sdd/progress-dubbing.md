# Dubbing & Translation Progress Ledger

Plan: `docs/superpowers/plans/2026-10-01-dubbing-translation.md`

## Status
- [x] Task 1: Suporte a Múltiplos Idiomas no Modelo e Banco de Dados
- [x] Task 2: Curador com Tradução e Adaptação de Roteiro para Português
- [x] Task 3: Sintetizador de Voz Neural com Edge-TTS
- [ ] Task 4: Mixagem de Áudio com Ducking no Renderizador FFmpeg
- [ ] Task 5: Roteamento de Episódios Internacionais no Orquestrador e CLI

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


