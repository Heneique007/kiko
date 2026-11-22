"""Configuration only; no credentials are ever exposed by the API."""
import os
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]


def integer(name, default, maximum):
    try:
        value = int(os.getenv(name, str(default)))
        if 1 <= value <= maximum:
            return value
    except ValueError:
        pass
    raise HTTPException(503, f'Configuração inválida: {name}.')


def origins():
    values = [v.strip().rstrip('/') for v in os.getenv('CORS_ORIGINS', '').split(',') if v.strip()]
    for value in values:
        u = urlsplit(value)
        if u.scheme not in ('http', 'https') or not u.netloc or u.path or u.query or u.fragment or '*' in value or u.username:
            raise RuntimeError('CORS_ORIGINS deve conter origens explícitas, sem caminhos.')
    return values


def allowed_uids():
    values = {v.strip() for v in os.getenv('KIKO_ALLOWED_UIDS', '').split(',') if v.strip()}
    if not values or len(values) > 4:
        raise HTTPException(503, 'Configure entre um e quatro UIDs autorizados no servidor.')
    return values


def limits():
    return {
        'max_file_bytes': integer('MAX_FILE_MB', 10, 30) * 1024 * 1024,
        'max_total_bytes': integer('MAX_TOTAL_MB', 50, 300) * 1024 * 1024,
        'max_files': integer('MAX_FILES', 20, 200),
        'file_ttl_hours': integer('FILE_TTL_HOURS', 6, 72),
        'max_doc_chars': integer('MAX_DOC_CHARS', 35000, 100000),
        'max_context_chars': integer('MAX_CONTEXT_CHARS', 120000, 300000),
        'max_attachments': integer('MAX_ATTACHMENTS', 4, 8),
    }
