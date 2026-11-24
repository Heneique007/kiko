import asyncio
import json
import os
import threading
from fastapi import Header, HTTPException, Request
import firebase_admin
from firebase_admin import auth, credentials
from .config import allowed_uids

_admin_lock = threading.Lock()


def admin_app():
    if os.getenv('FIREBASE_AUTH_EMULATOR_HOST'):
        raise HTTPException(503, 'Remova a configuração do emulador Firebase para usar esta aplicação.')
    with _admin_lock:
        try:
            return firebase_admin.get_app('kiko')
        except ValueError:
            project = os.getenv('FIREBASE_PROJECT_ID', '').strip()
            raw = os.getenv('FIREBASE_SERVICE_ACCOUNT_JSON', '').strip()
            path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '').strip()
            if not project or not (raw or path):
                raise HTTPException(503, 'Autenticação do servidor por configurar.')
            try:
                credential = credentials.Certificate(json.loads(raw) if raw else path)
                return firebase_admin.initialize_app(credential, {'projectId': project}, name='kiko')
            except Exception:
                raise HTTPException(503, 'Configuração Firebase inválida no servidor.') from None


def verify_token(token):
    app = admin_app()
    try:
        claims = auth.verify_id_token(token, app=app, check_revoked=True)
    except (auth.CertificateFetchError, auth.UnexpectedResponseError):
        raise HTTPException(503, 'Não foi possível verificar a sessão. Tente novamente.') from None
    except Exception:
        raise HTTPException(401, 'Sessão inválida ou expirada.', headers={'WWW-Authenticate': 'Bearer'}) from None
    if claims.get('firebase', {}).get('sign_in_provider') != 'password':
        raise HTTPException(403, 'Utilize uma conta de email e palavra-passe autorizada.')
    return claims


async def current_user(request: Request, authorization: str | None = Header(default=None)):
    if getattr(request.state, 'user', None):
        return request.state.user
    if not authorization or not authorization.startswith('Bearer ') or not 1 <= len(authorization[7:]) <= 16000:
        raise HTTPException(401, 'Inicie sessão para continuar.', headers={'WWW-Authenticate': 'Bearer'})
    claims = await asyncio.to_thread(verify_token, authorization[7:])
    if claims.get('uid') not in allowed_uids():
        raise HTTPException(403, 'Esta conta não está autorizada a utilizar a KIKO.')
    request.state.user = claims
    return claims
