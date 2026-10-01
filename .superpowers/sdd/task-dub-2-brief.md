# Task Dub-2 Brief: Curador com Tradução e Adaptação de Roteiro para Português

## Objetivos
Expandir o `CuratorAnalyzer` e `ClipMetadata` para suportar tradução e adaptação de roteiro de podcasts internacionais em inglês para português brasileiro oral, natural e dinâmico.

## Arquivos a modificar
1. `src/curator/analyzer.py`:
   - Em `ClipMetadata`:
     - Adicionar `translated_script: Optional[str] = None`
     - Adicionar `voice_gender: str = "male"`
   - Em `parse_llm_clip_response`:
     - Extrair `translated_script` e `voice_gender` (`male` ou `female`) dos itens do JSON.
   - Em `CuratorAnalyzer`:
     - Implementar o método:
       ```python
       def analyze_and_translate_transcript(
           self,
           transcript_formatted: Optional[str],
           max_clips: int = 3,
           min_duration: int = 45,
           max_duration: int = 90,
       ) -> List[ClipMetadata]:
       ```
     - O prompt deve instruir o Gemini a:
       1. Garimpar os momentos virais de podcasts internacionais.
       2. Traduzir o conteúdo para um roteiro falado em português brasileiro natural (`translated_script`), direto ao ponto, com cadência conversacional ideal para narração.
       3. Identificar o gênero do orador (`voice_gender`: 'male' ou 'female').
       4. Criar `hook_title` e `hashtags` em português.
2. `tests/test_curator.py`:
   - Adicionar testes verificando parsing de `translated_script` e `voice_gender`.
   - Testar `analyze_and_translate_transcript` com mock do Gemini.

## Critérios de Aceite
- Executar `pytest tests/test_curator.py -v` com 100% de sucesso.
- Executar toda a suíte `pytest tests/` garantindo zero regressões.
- Fazer commit: `feat: ai translation and script adaptation in curator analyzer`.
