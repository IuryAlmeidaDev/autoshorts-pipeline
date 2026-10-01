# Task 8 Brief: Publicadores Headless com Playwright (TikTok & Kwai)

## Objetivos
Construir os módulos de automação web baseados em Playwright para publicação no TikTok e no Kwai utilizando sessão autenticada persistente (`storage_state.json` / cookies exportados).

## Arquivos a criar
1. `src/publisher/tiktok.py`
2. `src/publisher/kwai.py`
3. `tests/test_browser_publishers.py`

## Especificações Técnicas

### 1. `src/publisher/tiktok.py`
- Classe `TikTokPublisher(BasePublisher)`:
  - `__init__(self, session_path: str | Path = "secrets/tiktok_session.json", headless: bool = True, timeout_sec: int = 60)`
  - Herda de `BasePublisher`.
  - Método `publish(video_path: Path | str, title: str, description: str = "", hashtags: list[str] = None) -> PublishResult`:
    - Valida existência do arquivo de vídeo e do arquivo de sessão (`session_path`).
    - Se a sessão não existir, retorna `PublishResult(success=False, platform='tiktok', error='Session file not found')`.
    - Inicializa Playwright Chromium com `storage_state=session_path`.
    - Navega até a central de criadores (`https://www.tiktok.com/creator-center/upload`).
    - Envia o arquivo no input de upload `input[type="file"]`.
    - Localiza o campo de legenda e digita o texto formatado (`format_caption`).
    - Clica no botão de postagem e aguarda confirmação de upload concluído.
    - Captura exceções (Timeout, seletor não encontrado, captcha) e retorna `PublishResult(success=False, platform='tiktok', error=str(e))`.

### 2. `src/publisher/kwai.py`
- Classe `KwaiPublisher(BasePublisher)`:
  - `__init__(self, session_path: str | Path = "secrets/kwai_session.json", headless: bool = True, timeout_sec: int = 60)`
  - Herda de `BasePublisher`.
  - Método `publish(video_path: Path | str, title: str, description: str = "", hashtags: list[str] = None) -> PublishResult`:
    - Validação de arquivos.
    - Inicializa Playwright com a sessão autenticada do Kwai Creator.
    - Faz upload do vídeo no input de arquivo e insere título/hashtags.
    - Submete a publicação e valida sucesso.
    - Retorna `PublishResult(success=True, platform='kwai')` ou captura erros.

### 3. Utilitário de Sessão (`src/publisher/session_helper.py` opcional ou embutido):
- Função para validar se o arquivo de sessão existe e é um JSON com cookies válidos.

## Testes (`tests/test_browser_publishers.py`)
- Testar validações de arquivos inexistentes (vídeo ou sessão).
- Testar fluxo de automação mockando `playwright.async_api` ou `playwright.sync_api` (`chromium.launch`, `new_context`, `page.goto`, `set_input_files`, `click`).
- Testar cenários de sucesso e captura de exceção com retorno seguro em `PublishResult`.

## Critérios de Aceite
- Executar `pytest tests/test_browser_publishers.py -v` com 100% de sucesso.
- Executar toda a suíte `pytest tests/` garantindo zero regressões.
- Git commit: `feat: headless browser publishers for tiktok and kwai`.
