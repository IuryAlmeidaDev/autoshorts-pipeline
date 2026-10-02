import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.database import Database
from src.config import settings
from src.publisher.youtube import YouTubeShortsPublisher

db = Database(settings.DB_PATH)
publisher = YouTubeShortsPublisher(
    client_secrets_file="secrets/youtube_client.json",
    credentials_file="secrets/youtube_token.json",
    privacy_status="unlisted"  # Seguro para você visualizar
)

pending_posts = db.get_pending_posts(platform="youtube_shorts")
print(f"Total de posts pendentes para YouTube Shorts: {len(pending_posts)}")

# Publicar os próximos 2 vídeos
published_count = 0
for post in pending_posts[:2]:
    clip = db.get_clip(post.clip_id)
    if not clip or not clip.file_path or not Path(clip.file_path).exists():
        continue
    
    print(f"\nPublicando corte {clip.id}: '{clip.hook_title}'...")
    print(f"Arquivo: {Path(clip.file_path).name}")
    
    res = publisher.publish(
        video_path=clip.file_path,
        title=f"{clip.hook_title} #Shorts",
        description=f"Corte imperdível! #Shorts #podcast #cortes #viral",
        hashtags=["#Shorts", "#podcast", "#cortes", "#viral"]
    )
    
    if res.success:
        db.update_post_status(post.id, status="posted", external_post_id=res.post_id)
        print(f"✅ SUCESSO! Link do Short: {res.url}")
        published_count += 1
    else:
        print(f"❌ Falha ao publicar: {res.error}")
        db.update_post_status(post.id, status="failed", error_log=res.error)

print(f"\nFinalizado! {published_count} novos vídeos publicados no seu canal.")
