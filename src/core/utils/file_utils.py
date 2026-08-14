import re

def sanitize_path_parts(origin: str) -> list[str]:
    """
    Splits a path/origin string by '/' and sanitizes each part 
    by replacing invalid filename characters with '_'.
    """
    if not origin:
        return []
    return [re.sub(r'[\\*?:"<>|]', "_", p) for p in origin.split("/")]

def format_storage_path(origin: str, filename: str) -> str:
    """
    Formata o caminho do arquivo para armazenamento (ex: /youtube/canal/arquivo.ext).
    """
    parts = sanitize_path_parts(origin)
    channel_path = "/".join(parts)
    if channel_path:
        return f"/youtube/{channel_path}/{filename}".replace("\\", "/")
    return f"/youtube/{filename}".replace("\\", "/")
