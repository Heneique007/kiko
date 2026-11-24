import { firebase, isConfigured } from './firebase.js';
import { $, messageError } from './ui.js';
import { request, friendly } from './api.js';

const errors = {
  'auth/invalid-credential': 'Email ou palavra-passe incorretos.',
  'auth/invalid-login-credentials': 'Email ou palavra-passe incorretos.',
  'auth/user-not-found': 'Email ou palavra-passe incorretos.',
  'auth/wrong-password': 'Email ou palavra-passe incorretos.',
  'auth/invalid-email': 'Introduza um endereço de email válido.',
  'auth/too-many-requests': 'Demasiadas tentativas. Aguarde antes de tentar novamente.',
  'auth/network-request-failed': 'Não foi possível contactar o Firebase. Verifique a ligação.',
  'auth/user-disabled': 'Esta conta está desativada.',
  'auth/operation-not-allowed': 'Ative Email/Password na configuração Firebase.',
  'auth/unauthorized-domain': 'Autorize este domínio na configuração Firebase.',
};
export async function setupAuth(chat) {
  let pending = false, authSequence = 0, retryTimer, retryDelay = 2000, retryAction = null;
  let sessionError = '';
  const loading = value => { pending = value; $('login-submit').disabled = value; $('login-submit').textContent = value ? 'A iniciar sessão…' : 'Iniciar sessão'; };
  const cancelRetry = () => { clearTimeout(retryTimer); retryAction = null; retryDelay = 2000; };
  const retry = action => {
    clearTimeout(retryTimer); retryAction = action;
    retryTimer = setTimeout(() => { const run = retryAction; retryAction = null; run?.(); }, retryDelay);
    retryDelay = Math.min(retryDelay * 2, 30000);
  };
  window.addEventListener('online', () => {
    if (retryAction) { const run = retryAction; clearTimeout(retryTimer); retryAction = null; run(); }
  });
  $('toggle-password').addEventListener('click', () => {
    const show = $('password').type === 'password'; $('password').type = show ? 'text' : 'password'; $('toggle-password').setAttribute('aria-pressed', String(show)); $('toggle-password').setAttribute('aria-label', show ? 'Ocultar palavra-passe' : 'Mostrar palavra-passe');
  });
  $('login-form').addEventListener('submit', async event => {
    event.preventDefault(); if (pending) return; loading(true); messageError('login-error', '');
    try { const { auth, sdk } = await firebase(); await sdk.signInWithEmailAndPassword(auth, $('email').value.trim(), $('password').value); $('password').value = ''; }
    catch (error) { messageError('login-error', errors[error.code] || friendly(error)); loading(false); }
  });
  if (!isConfigured()) { messageError('login-error', 'A KIKO precisa de configuração inicial. Defina o Firebase e o endereço da API em js/config.js, seguindo SETUP_PT.md.', true); return; }
  const invalidSession = error => error.status === 401 || error.status === 403 || ['auth/user-disabled', 'auth/user-token-expired', 'auth/invalid-user-token', 'auth/user-not-found'].includes(error.code);
  async function connect() {
    loading(true);
    try {
      const { auth, sdk } = await firebase();
      sdk.onAuthStateChanged(auth, async user => {
        const seq = ++authSequence; cancelRetry();
        chat.ready = false; chat.reset(); $('chat-view').hidden = true; $('login-view').hidden = false;
        $('attach-button').disabled = true;
        if (!user) { messageError('login-error', sessionError); sessionError = ''; loading(false); return; }
        async function validate() {
          if (seq !== authSequence) return;
          loading(true);
          try {
            let me;
            try { me = await request('/api/me'); }
            catch (error) {
              if (error.status !== 401) throw error;
              // A cached token may have expired; ask Firebase for a fresh one once.
              me = await request('/api/me', { forceTokenRefresh: true });
            }
            if (seq !== authSequence) return;
            cancelRetry(); chat.configure(me); $('login-view').hidden = true; $('chat-view').hidden = false; messageError('login-error', ''); loading(false);
          } catch (error) {
            if (seq !== authSequence) return;
            if (invalidSession(error)) {
              cancelRetry(); sessionError = error.status === 403 ? friendly(error) : (errors[error.code] || 'A sessão terminou. Inicie sessão novamente.');
              messageError('login-error', sessionError);
              try { await sdk.signOut(auth); } catch { /* Keep access blocked if local sign-out fails. */ }
              if (seq === authSequence) loading(false);
            } else {
              // Render cold starts, offline use and temporary Firebase errors do not erase the session.
              messageError('login-error', 'Não foi possível validar a sessão. A KIKO vai tentar novamente automaticamente.', true);
              retry(validate);
            }
          }
        }
        await validate();
      });
    } catch (error) {
      messageError('login-error', errors[error.code] || friendly(error));
      retry(connect);
    }
  }
  await connect();
}
