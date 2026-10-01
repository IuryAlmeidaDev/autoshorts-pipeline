# Task Dub-5 Brief: Roteamento de Episódios Internacionais no Orquestrador e CLI

## Objetivos
Integrar o fluxo de dublagem ao `PipelineOrchestrator` de forma automática para qualquer canal cadastrado com idioma inglês (`language="en"`), e adicionar a flag `--lang` no comando CLI `main.py add-channel`.

## Arquivos a modificar
1. `src/orchestrator.py`:
   - Importar `VoiceSynthesizer` de `src.dubbing`.
   - No `__init__`: aceitar `voice_synthesizer: Optional[VoiceSynthesizer] = None` com default para `VoiceSynthesizer(temp_dir=settings.TEMP_DIR)`.
   - No `process_episode(episode)`:
     - Obter canal no banco (`channel = self.db.get_channel(episode.channel_id)`).
     - Se `channel and channel.language == "en"`:
       - Extrair transcrição em inglês: `languages=["en", "en-US"]`.
       - Chamar `self.curator.analyze_and_translate_transcript(transcript_formatted, ...)` obtendo `ClipMetadata` com `translated_script` e `voice_gender`.
       - Para cada clipe:
         - Baixar corte bruto via `self.downloader`.
         - Se houver `translated_script`:
           - Sintetizar áudio e obter palavras com timestamps via `self.voice_synthesizer.synthesize(clip_meta.translated_script, voice_gender=clip_meta.voice_gender)`.
           - Renderizar com `self.renderer.render_clip(..., words=words, dubbing_audio=dubbing_audio, ducking_volume=0.15)`.
           - Limpar arquivo de dublagem temporário.
         - Se não houver `translated_script`: fallback para fluxo normal com legendas.
     - Se `channel.language != "en"`:
       - Executar o fluxo nacional padrão já existente.
2. `main.py`:
   - No `add-channel` subparser:
     - Adicionar argumento opcional `--lang` (ou `--language`) com `default="pt"` e `choices=["pt", "en"]`.
     - Chamar `db.add_channel(channel_id=channel_id, name=name, language=args.lang)`.
3. `tests/test_orchestrator.py`:
   - Adicionar testes verificando:
     - Processamento de episódio de canal em inglês invocando `analyze_and_translate_transcript`, síntese de voz e renderização com `dubbing_audio`.
     - Preservação do fluxo nacional quando canal for `pt`.
     - Teste de CLI `add-channel` passando flag `--lang en`.

## Critérios de Aceite
- Executar `pytest tests/test_orchestrator.py -v` com 100% de sucesso.
- Executar toda a suíte `pytest tests/` garantindo zero regressões.
- Fazer commit: `feat: international episode dubbing routing and cli language flag`.
