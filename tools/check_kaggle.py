"""Print only actual model IDs. Never print proxy URLs or temporary secrets."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from dotenv import load_dotenv
from app.kaggle import obtain


def main():
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    if not os.getenv('KAGGLE_API_TOKEN', '').strip():
        print('Defina KAGGLE_API_TOKEN no ambiente ou no ficheiro .env privado.', file=sys.stderr)
        return 1
    try:
        data = obtain()
    except Exception:
        print('Não foi possível obter a lista real. Confirme o token, o acesso e a instalação do CLI Kaggle.', file=sys.stderr)
        return 1
    print('Modelos disponíveis nas credenciais atuais:')
    for model in data['models']:
        print(model)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
