import os
from pathlib import Path
from fastapi import HTTPException
from .config import ROOT

MODES = ('learn', 'think', 'quick')


def load_prompt(mode):
    if mode not in MODES:
        raise HTTPException(422, 'Modo inválido.')
    production = os.getenv('KIKO_ENV', 'production') != 'development'
    configured = os.getenv('KIKO_PROMPTS_DIR', '').strip()
    # Explicit configuration is authoritative: do not hide mistakes with a fallback.
    if configured:
        paths = [Path(configured) / f'{mode}.txt']
    else:
        paths = [Path('/etc/secrets') / f'{mode}.txt']
        if not production:
            paths.append(ROOT / 'prompts-private' / f'{mode}.txt')
    if not production and os.getenv('KIKO_ALLOW_EXAMPLE_PROMPTS') == 'true':
        paths.append(ROOT / 'prompts' / f'{mode}.example.txt')
    for path in paths:
        try:
            if path.is_file():
                text = path.read_text(encoding='utf-8').strip()
                if not text or len(text) > 30000:
                    break
                return text
        except (OSError, UnicodeError):
            break
    raise HTTPException(503, 'Prompt do modo por configurar no servidor. Contacte o administrador.')
