# Task 3 Brief: Scout & YouTube RSS Monitor

## Objetivos
Construir o módulo de monitoramento de canais do YouTube sem consumo de cota de API, utilizando os feeds RSS/Atom oficiais (`https://www.youtube.com/feeds/videos.xml?channel_id=...`).

## Arquivos a criar
1. `src/scout/__init__.py`
2. `src/scout/monitor.py`
3. `tests/test_scout.py`

## Especificação Técnica (`src/scout/monitor.py`)

1. Dataclass `Episode`:
   - `video_id: str`
   - `channel_id: str`
   - `title: str`
   - `published_at: datetime`
   - `link: str`

2. Funções / Classes:
   - `parse_youtube_feed(feed_content: str) -> list[Episode]`:
     - Usa `xml.etree.ElementTree` ou `feedparser` para extrair entradas do XML padrão do YouTube.
     - YouTube Atom XML namespaces:
       - `feed = {default: 'http://www.w3.org/2005/Atom', 'yt': 'http://www.youtube.com/xml/schemas/2015'}`
       - `<yt:videoId>`, `<yt:channelId>`, `<title>`, `<published>`, `<link rel="alternate" href="...">`.
     - Tratamento seguro de feeds vazios, tags ausentes ou XML malformatado.
   - `fetch_channel_feed(channel_id: str, timeout: int = 15) -> str`:
     - Faz requisição HTTP GET para `https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}` com User-Agent padrão de navegador.
     - Lança erro tratado ou retorna string vazia em caso de falha de conexão.
   - `ScoutMonitor`:
     - `__init__(self, db: Database)`
     - `scan_all_channels() -> list[Episode]`:
       - Busca canais ativos no banco (`db.get_active_channels()`).
       - Para cada canal, obtém o feed e analisa os episódios.
       - Filtra apenas os vídeos que **ainda não foram processados** (`not db.is_video_processed(ep.video_id)`).
       - Retorna lista ordenada de episódios novos a processar.

## Testes (`tests/test_scout.py`)
- Testar `parse_youtube_feed` com XML mockado válido contendo múltiplos episódios.
- Testar `parse_youtube_feed` com XML vazio ou malformado (deve retornar lista vazia sem explodir).
- Testar `ScoutMonitor.scan_all_channels` com mocks para simular HTTP e validar filtragem de vídeos já processados no banco.

## Critérios de Aceite
- Executar `pytest tests/test_scout.py -v` com 100% de sucesso.
- Executar toda a suíte `pytest tests/` garantindo zero regressões.
- Git commit: `feat: youtube rss scout monitor`.
