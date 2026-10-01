# Imagem base Python 3.11 slim otimizada para Linux VPS
FROM python:3.11-slim

# Evita geração de bytecode e garante stdout sem buffer
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Instalação de utilitários essenciais, FFmpeg e fontes TrueType de alta visibilidade
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-dejavu-core \
    fonts-freefont-ttf \
    fonts-montserrat \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalação de dependências Python
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Instalação do navegador Chromium e dependências de sistema do Playwright
RUN playwright install --with-deps chromium

# Copia o código-fonte da aplicação
COPY . /app

# Garante a existência das pastas de persistência
RUN mkdir -p /app/storage/temp /app/storage/output /app/secrets

# Declaração dos volumes de dados persistentes
VOLUME ["/app/storage", "/app/secrets"]

# Ponto de entrada padrão: agendador 24/7
CMD ["python", "main.py", "run"]
