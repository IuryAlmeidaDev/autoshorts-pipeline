# Task Dub-1 Brief: Suporte a Múltiplos Idiomas no Modelo e Banco de Dados

## Objetivos
Adicionar suporte ao campo de idioma (`language`) no modelo `Channel` e no repositório `Database` para diferenciar canais em português (`pt`) de canais internacionais (`en`).

## Arquivos a modificar
1. `src/models.py`:
   - Adicionar campo `language: str = "pt"` em `Channel`.
2. `src/database.py`:
   - No `init_db()`: criar tabela `channels` com coluna `language TEXT DEFAULT 'pt'` e executar migração idempotente:
     ```python
     cursor.execute("PRAGMA table_info(channels)")
     cols = [c[1] for c in cursor.fetchall()]
     if "language" not in cols:
         cursor.execute("ALTER TABLE channels ADD COLUMN language TEXT DEFAULT 'pt'")
     ```
   - Atualizar `add_channel(self, channel_id: str, name: str, language: str = "pt") -> Channel`.
   - Atualizar `get_active_channels(self, language: Optional[str] = None) -> list[Channel]`.
3. `tests/test_database.py`:
   - Adicionar testes verificando criação de canal com idioma customizado, valor default `'pt'`, e filtragem por idioma em `get_active_channels`.

## Critérios de Aceite
- Executar `pytest tests/test_database.py -v` com 100% de sucesso.
- Executar toda a suíte `pytest tests/` garantindo zero regressões.
- Fazer commit: `feat: add multi-language support to channel model and database`.
