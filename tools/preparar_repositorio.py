"""Copy versioned templates to the exact paths required by GitHub and Git."""
from pathlib import Path
from shutil import copyfile

root = Path(__file__).resolve().parents[1]
files = {
    'configuracao/github/workflows/test.yml': '.github/workflows/test.yml',
    'configuracao/github/workflows/pages.yml': '.github/workflows/pages.yml',
    'configuracao/gitignore.txt': '.gitignore',
}
for src, dest in files.items():
    target = root / dest
    target.parent.mkdir(parents=True, exist_ok=True)
    copyfile(root / src, target)
    print(f'Atualizado: {dest}')
