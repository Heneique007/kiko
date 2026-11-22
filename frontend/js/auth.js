import { firebase, isConfigured } from './firebase.js';
import { $, messageError, toast } from './ui.js';
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
  const loading = value => { pending = value; $('login-submit').disabled = value; $('login-submit').firstChild.textContent = value ? 'A iniciar sessão… ' : 'Iniciar sessão '; };
  $('toggle-password').addEventListener('click', () => {
    const show = $('password').type === 'password'; $('password').type = show ? 'text' : 'password'; $('toggle-password').setAttribute('aria-pressed', String(show)); $('toggle-password').setAttribute('aria-label', show ? 'Ocultar palavra-passe' : 'Mostrar palavra-passe');
  });
  $('account-toggle').addEventListener('click', () => { $('account-menu').hidden = !$('account-menu').hidden; $('account-toggle').setAttribute('aria-expanded', String(!$('account-menu').hidden)); });
  const closeMenu = () => { $('account-menu').hidden = true; $('account-toggle').setAttribute('aria-expanded', 'false'); };
  document.addEventListener('click', event => { if (!event.target.closest('.account-wrap')) closeMenu(); });
  document.addEventListener('keydown', event => { if (event.key === 'Escape') closeMenu(); });
  $('logout').addEventListener('click', async () => {
    closeMenu(); chat.ready = false; chat.reset(); const { auth, sdk } = await firebase(); await sdk.signOut(auth); toast('Sessão terminada.');
  });
  $('login-form').addEventListener('submit', async event => {
    event.preventDefault(); if (pending) return; loading(true); messageError('login-error', '');
    try { const { auth, sdk } = await firebase(); await sdk.signInWithEmailAndPassword(auth, $('email').value.trim(), $('password').value); $('password').value = ''; }
    catch (error) { messageError('login-error', errors[error.code] || friendly(error)); loading(false); }
  });
  $('reset-password').addEventListener('click', async () => {
    if (!$('email').value || !$('email').checkValidity()) { messageError('login-error', 'Introduza primeiro o seu endereço de email.'); $('email').focus(); return; }
    $('reset-password').disabled = true;
    try { const { auth, sdk } = await firebase(); await sdk.sendPasswordResetEmail(auth, $('email').value.trim()); messageError('login-error', 'Se existir uma conta elegível, receberá um email de recuperação.', true); }
    catch (error) { messageError('login-error', errors[error.code] || friendly(error)); }
    finally { $('reset-password').disabled = false; }
  });
  if (!isConfigured()) { messageError('login-error', 'A KIKO precisa de configuração inicial. Defina o Firebase e o endereço da API em js/config.js, seguindo SETUP_PT.md.', true); return; }
  try {
    const { auth, sdk } = await firebase();
    sdk.onAuthStateChanged(auth, async user => {
      const seq = ++authSequence;
      chat.ready = false; chat.reset(); $('chat-view').hidden = true; $('login-view').hidden = false;
      $('attach-button').disabled = true; $('file-limits').disabled = true;
      if (!user) { loading(false); return; }
      loading(true);
      try {
        const me = await request('/api/me');
        if (seq !== authSequence) return;
        chat.configure(me); $('account-email').textContent = me.email || user.email; $('login-view').hidden = true; $('chat-view').hidden = false; messageError('login-error', '');
      } catch (error) {
        if (seq !== authSequence) return;
        await sdk.signOut(auth); messageError('login-error', friendly(error));
      } finally { if (seq === authSequence) loading(false); }
    });
  } catch (error) { messageError('login-error', errors[error.code] || friendly(error)); loading(false); }
}
