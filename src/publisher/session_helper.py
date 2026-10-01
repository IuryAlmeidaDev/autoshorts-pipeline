"""Utilitários para validação e persistência de sessões de autenticação do Playwright."""

import json
import logging
from pathlib import Path
from typing import Optional, Tuple, Union

logger = logging.getLogger(__name__)


def validate_session_file(session_path: Union[str, Path]) -> Tuple[bool, Optional[str]]:
    """Valida se o arquivo de sessão existe, é legível e contém dados de autenticação válidos.

    Args:
        session_path: Caminho para o arquivo storage_state.json ou lista de cookies.

    Returns:
        Tupla (is_valid: bool, error_message: Optional[str]).
    """
    path = Path(session_path)

    if not path.exists():
        return False, f"Session file not found: {path}"

    if not path.is_file():
        return False, f"Session path is not a file: {path}"

    try:
        content = path.read_text(encoding="utf-8").strip()
    except Exception as e:
        return False, f"Failed to read session file: {e}"

    if not content:
        return False, "Session file is empty"

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON in session file: {e}"

    # Validação do formato padrão do Playwright: {"cookies": [...], "origins": [...]}
    if isinstance(data, dict):
        if "cookies" not in data or not isinstance(data["cookies"], list):
            return False, "Session JSON missing 'cookies' list"
        return True, None

    # Validação de formato alternativo: lista direta de cookies [{"name": ...}, ...]
    if isinstance(data, list):
        if len(data) == 0 or not all(isinstance(c, dict) and "name" in c for c in data):
            return False, "Session JSON list missing cookie entries"
        return True, None

    return False, "Invalid session JSON structure: must be dict with 'cookies' or list of cookies"


def save_session_state(data: Union[dict, list], session_path: Union[str, Path]) -> Path:
    """Salva estado de sessão no formato JSON garantindo que o diretório pai exista.

    Args:
        data: Dicionário ou lista de cookies.
        session_path: Caminho destino.

    Returns:
        Path para o arquivo gravado.
    """
    path = Path(session_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
