"""Modelos de dados para o gerador de histórias do Reddit."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class RedditStory:
    """Estrutura de dados representando uma história do Reddit para Shorts/TikTok."""

    title: str
    subreddit: str = "r/desabafos"
    author: str = "u/anonimo_1994"
    upvotes: str = "14.8k"
    comments_count: str = "1.2k"
    hook_text: str = ""
    full_script: str = ""
    tags: List[str] = field(default_factory=lambda: ["#Shorts", "#reddit", "#historiasdoreddit", "#tiktok"])

    def __post_init__(self):
        if not self.hook_text and self.title:
            self.hook_text = self.title
        if not self.full_script:
            self.full_script = self.title
