import { Chat } from './chat.js';
import { setupAuth } from './auth.js';
import { setupViewport, toast } from './ui.js';
setupViewport();
const chat = new Chat();
setupAuth(chat).catch(() => toast('Não foi possível iniciar a autenticação. Atualize a página.'));
if ('serviceWorker' in navigator && (location.protocol === 'https:' || ['localhost', '127.0.0.1'].includes(location.hostname))) {
  navigator.serviceWorker.register('./sw.js', { scope: './' }).catch(() => { /* Online functionality remains available without installation. */ });
}
