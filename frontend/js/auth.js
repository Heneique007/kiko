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
  let pending = false; let authSequence = 0;
  const loading = value => { pending = value; $('login-submit').disabled = value; $('login-submit').textContent = value ? 'A iniciar sessão…' : 'Iniciar sessão'; };
  $('toggle-password').addEventListener('click', () => {
    const show = $('password').type === 'password'; $('password').type = show ? 'text' : 'password'; $('toggle-password').setAttribute('aria-pressed', String(show)); $('toggle-password').setAttribute('aria-label', show ? 'Ocultar palavra-passe' : 'Mostrar palavra-passe');
  });
  $('login-form').addEventListener('submit', async event => {
    event.preventDefault(); if (pending) return; loading(true); messageError('login-error', '');
    try { const { auth, sdk } = await firebase(); await sdk.signInWithEmailAndPassword(auth, $('email').value.trim(), $('password').value); $('password').value = ''; }
    catch (error) { messageError('login-error', errors[error.code] || friendly(error)); loading(false); }
  });
  if (!isConfigured()) { messageError('login-error', 'A KIKO precisa de configuração inicial. Defina o Firebase e o endereço da API em js/config.js, seguindo SETUP_PT.md.', true); return; }
  try {
    const { auth, sdk } = await firebase();
    sdk.onAuthStateChanged(auth, async user => {
      const seq = ++authSequence;
      chat.ready = false; chat.reset(); $('chat-view').hidden = true; $('login-view').hidden = false;
      $('attach-button').disabled = true;
      if (!user) { loading(false); return; }
      loading(true);
      try {
        const me = await request('/api/me');
        if (seq !== authSequence) return;
        chat.configure(me); $('login-view').hidden = true; $('chat-view').hidden = false; messageError('login-error', '');
      } catch (error) {
        if (seq !== authSequence) return;
        await sdk.signOut(auth); messageError('login-error', friendly(error));
      } finally { if (seq === authSequence) loading(false); }
    });
  } catch (error) { messageError('login-error', errors[error.code] || friendly(error)); loading(false); }
}
