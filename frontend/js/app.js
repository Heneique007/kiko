import { Chat } from './chat.js';
import { setupAuth } from './auth.js';
import { setupViewport, toast } from './ui.js';
import { setupVersion } from './version.js';
setupViewport();
const chat = new Chat();
setupAuth(chat).catch(() => toast('Não foi possível iniciar a autenticação. Atualize a página.'));
setupVersion(chat);
