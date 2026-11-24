"""Check the real Pages artifact, including its generated cache manifest."""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as tmp:
    out = Path(tmp) / 'dist'
    meta = Path(tmp) / 'backend.json'
    subprocess.run([sys.executable, str(ROOT / 'tools/build_frontend.py'), '--output', str(out)], check=True)
    subprocess.run([sys.executable, str(ROOT / 'tools/build_frontend.py'), '--metadata', str(meta)], check=True)
    published = json.loads((out / 'version.json').read_text())
    assert published == json.loads(meta.read_text())
    build = published['build']
    assert re.fullmatch(r'[a-f0-9]{24}', build)
    html = (out / 'index.html').read_text()
    assert f'name="kiko-build" content="{build}"' in html
    assert 'id="app-version"' in html and 'O KIKO está em desenvolvimento. Pode cometer erros' in html
    for old in ('ESPAÇO PRIVADO', 'UM ESPAÇO. TRÊS FORMAS', 'Uma pergunta é sempre um bom começo', 'Limites dos anexos', 'mode-cards', 'id="logout"'):
        assert old not in html
    for href in re.findall(r'(?:src|href)="(\./[^\"]+)"', html):
        assert (out / href).is_file(), href
        if href.startswith(('./css/', './js/', './assets/')):
            raise AssertionError(f'Unversioned resource: {href}')
    sw = (out / 'sw.js').read_text()
    assert f"const BUILD = '{build}';" in sw
    for href in re.findall(r"'(\./[^']+)'", sw):
        assert (out / href).exists(), href
    for icon in json.loads((out / 'manifest.webmanifest').read_text())['icons']:
        assert (out / icon['src']).is_file()
    for relative in ('js/app.js', 'js/version.js', 'css/style.css', 'assets/wordmark.png'):
        assert (out / 'releases' / build / relative).read_bytes() == (ROOT / 'frontend' / relative).read_bytes()
    print('Pages build: hash idêntico ao Render, todos os recursos presentes, layout novo confirmado.')
