import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.publisher.youtube import YouTubeShortsPublisher
from src.config import settings

print("=== CONECTANDO AO YOUTUBE E PUBLICANDO O PRIMEIRO VÍDEO ===")
print("1. Abrindo o navegador para autorizar o canal...")

# Set up publisher
publisher = YouTubeShortsPublisher(
    client_secrets_file="secrets/youtube_client.json",
    credentials_file="secrets/youtube_token.json",
    privacy_status="unlisted"  # 'unlisted' para você assistir e aprovar com segurança primeiro
)

video_path = Path("storage/output/7JUproZnBMI_1_45_115.mp4")
if not video_path.exists():
    # Fallback to demo video
    video_path = Path("storage/output/corte_viral_demonstracao.mp4")

print(f"2. Vídeo selecionado para upload: {video_path.name}")
print("3. Iniciando upload para o YouTube Shorts...")

result = publisher.publish(
    video_path=video_path,
    title="O BRASIL É UM EXPORTADOR DE CÉREBROS! #Shorts",
    description="Reflexão profunda sobre a educação e talentos no Brasil. #Shorts #educacao #podcast #brasil #augustocury",
    hashtags=["#Shorts", "#educacao", "#podcast", "#brasil"]
)

if result.success:
    print("\n🎉 SUCESSO TOTAL! O VÍDEO FOI PUBLICADO NO YOUTUBE!")
    print(f"👉 Link para assistir agora: {result.url}")
    print(f"ID do vídeo: {result.post_id}")
else:
    print(f"\n❌ Erro durante a publicação: {result.error}")
