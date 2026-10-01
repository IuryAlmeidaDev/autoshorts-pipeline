# AutoShorts Pipeline 🚀

Pipeline 100% autônomo em Python / Docker para minerar podcasts no YouTube, encontrar os momentos mais virais via IA (Gemini), recortar e reenquadrar em formato vertical (9:16) com legendas dinâmicas animadas (estilo karaokê/Hormozi) e publicar automaticamente no **YouTube Shorts**, **TikTok**, **Instagram Reels** e **Kwai**.

---

## 🏗️ Arquitetura do Sistema

```
  +──────────────────────────────────────────────────────────+
  |                   AutoShorts Pipeline                     |
  |                                                          |
  |  [Scout Monitor] ──> [IA Curadora] ──> [Motor de Vídeo]  |
  |   (Feed RSS YT)       (Gemini LLM)     (yt-dlp + FFmpeg) |
  |                                                │         |
  |                                                ▼         |
  |        [Publicadores Oficiais e Headless Browser]        |
  |      YouTube Shorts | TikTok | Instagram Reels | Kwai     |
  +──────────────────────────────────────────────────────────+
```

1. **Scout Monitor:** Monitora canais via feeds RSS do YouTube (sem consumir cotas de API).
2. **IA Curadora:** Extrai a transcrição e usa o Gemini Flash para pontuar e eleger os momentos virais (45s a 90s) com gancho e hashtags.
3. **Motor de Vídeo:**
   - Download cirúrgico apenas do trecho selecionado com `yt-dlp`.
   - Extração de legendas dinâmicas palavra por palavra com Whisper.
   - Enquadramento vertical 9:16 (modo `smart_crop` ou `blurred_background`).
   - Inserção de gancho chamativo no topo e legendas no estilo karaokê via FFmpeg.
4. **Publicador Multi-Rede:**
   - **YouTube Shorts:** YouTube Data API v3 com upload resumable.
   - **Instagram Reels:** Meta Graph API oficial (ciclo de containers).
   - **TikTok & Kwai:** Automação headless Playwright com cookies e sessão persistente.

---

## 🚀 Como Executar

### 1. Configurar Variáveis de Ambiente
Copie o arquivo de exemplo e preencha suas chaves:
```bash
cp .env.example .env
```

Campos no `.env`:
- `GEMINI_API_KEY`: Sua chave gratuita do Google AI Studio.
- `POLL_INTERVAL_MINUTES`: Intervalo de verificação de novos podcasts (padrão: 60 min).
- `POST_INTERVAL_HOURS`: Espaçamento seguro entre postagens nas redes (padrão: 4 horas).
- `INSTAGRAM_ACCESS_TOKEN` e `INSTAGRAM_ACCOUNT_ID`: Tokens da Meta Graph API para Reels.

### 2. Configurar Sessões e Credenciais (`secrets/`)
Crie a pasta `secrets/` se não existir:
- **YouTube Shorts:** Salve seu arquivo OAuth2 baixado do Google Cloud Console em `secrets/youtube_client.json`.
- **TikTok:** Exporte os cookies/sessão da sua conta em `secrets/tiktok_session.json` (formato Playwright `storage_state`).
- **Kwai:** Exporte os cookies da sua conta em `secrets/kwai_session.json`.

---

## 💻 Comandos CLI

### Cadastrar Canais para Monitoramento:
```bash
# Exemplo: Cadastrar o Podpah ou Flow
python main.py add-channel UC4rXv44_tB5m4eB9i0jCq1g "Podpah Podcast"
```

### Executar uma Rodada Manual Imediata:
```bash
python main.py once
```

### Iniciar o Robô 24/7 (Scheduler Contínuo):
```bash
python main.py run
```

---

## 🐳 Executando com Docker na Nuvem (VPS Linux)

O projeto já inclui `Dockerfile` com FFmpeg, fontes TrueType e navegador Chromium do Playwright pré-instalados.

```bash
# Subir o pipeline em segundo plano
docker compose up -d --build

# Ver logs da execução
docker compose logs -f
```

---

## 🧪 Suíte de Testes
O projeto conta com 100% de cobertura nos componentes através de TDD:
```bash
pytest -v
```
