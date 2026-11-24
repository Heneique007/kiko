"""Build deterministic, content-addressed public frontend (no secrets)."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'frontend'


def metadata():
    digest = hashlib.sha256()
    for path in sorted(p for p in SOURCE.rglob('*') if p.is_file()):
        digest.update(path.relative_to(SOURCE).as_posix().encode() + b'\0')
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    digest.update(Path(__file__).read_bytes())
    version = json.loads((SOURCE / 'version.json').read_text())['version']
    return {'version': version, 'build': digest.hexdigest()[:24]}


def build(output):
    info = metadata()
    output = output.resolve()
    if output == SOURCE or SOURCE in output.parents or output in SOURCE.parents:
        raise ValueError('Choose an output directory outside the frontend source tree.')
    output.mkdir(parents=True, exist_ok=True)
    prefix = f'./releases/{info["build"]}/'
    release = output / 'releases' / info['build']
    for name in ('css', 'js', 'assets'):
        shutil.copytree(SOURCE / name, release / name, dirs_exist_ok=True)
    def rewrite(text):
        for directory in ('css', 'js', 'assets'):
            text = text.replace(f'./{directory}/', prefix + directory + '/')
        return text
    html = rewrite((SOURCE / 'index.html').read_text())
    html = html.replace('name="kiko-build" content="source"', f'name="kiko-build" content="{info["build"]}"')
    (output / 'index.html').write_text(html)
    (output / 'manifest.webmanifest').write_text(rewrite((SOURCE / 'manifest.webmanifest').read_text()))
    sw = rewrite((SOURCE / 'sw.js').read_text()).replace("const BUILD = 'source';", f'const BUILD = \'{info["build"]}\';')
    (output / 'sw.js').write_text(sw)
    (output / 'version.json').write_text(json.dumps(info) + '\n')
    print(json.dumps(info))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--output', type=Path)
    group.add_argument('--metadata', type=Path)
    args = parser.parse_args()
    if args.metadata:
        args.metadata.write_text(json.dumps(metadata()) + '\n')
    else:
        build(args.output)
