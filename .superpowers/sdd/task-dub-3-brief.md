# Task Dub-3 Brief: Sintetizador de Voz Neural com Edge-TTS

## Objetivos
Criar o módulo `src/dubbing/voice_synthesizer.py` que utiliza a biblioteca `edge-tts` para converter o roteiro traduzido em áudio falado natural em português brasileiro com vozes neurais e extração de timestamps palavra por palavra para geração de legendas animadas.

## Arquivos a criar
1. `src/dubbing/__init__.py`
2. `src/dubbing/voice_synthesizer.py`
3. `tests/test_dubbing.py`

## Especificações Técnicas (`src/dubbing/voice_synthesizer.py`)

1. Exceção `VoiceSynthesisError(Exception)`.

2. Mapeamento de Vozes:
   - `DEFAULT_MALE_VOICE = "pt-BR-AntonioNeural"`
   - `DEFAULT_FEMALE_VOICE = "pt-BR-FranciscaNeural"`

3. Classe `VoiceSynthesizer`:
   - `__init__(self, temp_dir: Optional[Path | str] = None, male_voice: str = DEFAULT_MALE_VOICE, female_voice: str = DEFAULT_FEMALE_VOICE)`
   - `get_voice_for_gender(self, gender: str) -> str`:
     - Retorna `female_voice` se `gender.lower() == "female"`, senão `male_voice`.
   - `async def synthesize_async(self, text: str, voice_gender: str = "male", output_filename: Optional[str] = None) -> tuple[Path, list[WordTimestamp]]`:
     - Valida `text` (não pode ser vazio).
     - Instancia `edge_tts.Communicate(text, voice)`.
     - Itera sobre `communicate.stream()`:
       - Para pacotes de áudio (`chunk["type"] == "audio"`): grava bytes no arquivo temporário `.mp3`.
       - Para `chunk["type"] == "WordBoundary"`:
         - `start = chunk["offset"] / 10_000_000.0`
         - `end = (chunk["offset"] + chunk["duration"]) / 10_000_000.0`
         - `word = chunk["text"]`
         - Adiciona `WordTimestamp(word=word, start=start, end=end)`.
     - Retorna `(audio_path, words)`.
   - `synthesize(self, text: str, voice_gender: str = "male", output_filename: Optional[str] = None) -> tuple[Path, list[WordTimestamp]]`:
     - Invoca `asyncio.run(self.synthesize_async(...))` para permitir chamada síncrona simples a partir do pipeline.

## Testes (`tests/test_dubbing.py`)
- Testar seleção de voz por gênero (male/female/default).
- Testar validações de texto vazio/inválido levantando `VoiceSynthesisError` ou `ValueError`.
- Testar `synthesize` com mock de `edge_tts.Communicate.stream()` validando retorno de arquivo e instâncias de `WordTimestamp`.
- Testar tratamento de exceções de conexão ou streaming.

## Critérios de Aceite
- Executar `pytest tests/test_dubbing.py -v` com 100% de sucesso.
- Executar toda a suíte `pytest tests/` garantindo zero regressões.
- Fazer commit: `feat: neural voice synthesizer with edge-tts and word timestamps`.
