import { config } from './config.js';
let promise;

export function isConfigured() {
  try {
    const url = new URL(config.apiBaseUrl);
    return (url.protocol === 'https:' || (url.protocol === 'http:' && ['localhost', '127.0.0.1'].includes(url.hostname))) &&
      !url.username && !url.password && !url.search && !url.hash && (!url.pathname || url.pathname === '/') &&
      ['apiKey', 'authDomain', 'projectId', 'appId'].every(key => typeof config.firebase[key] === 'string' && config.firebase[key].trim());
  } catch { return false; }
}

export async function firebase() {
  if (!isConfigured()) throw new Error('Configure o Firebase e o endereço do servidor em js/config.js. Consulte SETUP_PT.md.');
  if (!promise) promise = (async () => {
    const [{ initializeApp }, sdk] = await Promise.all([
      import('https://www.gstatic.com/firebasejs/13.4.0/firebase-app.js'),
      import('https://www.gstatic.com/firebasejs/13.4.0/firebase-auth.js'),
    ]);
    const auth = sdk.getAuth(initializeApp(config.firebase));
    auth.languageCode = 'pt';
    await sdk.setPersistence(auth, sdk.browserSessionPersistence);
    return { auth, sdk };
  })().catch(error => { promise = null; throw error; });
  return promise;
}

export async function token(force = false) {
  const { auth } = await firebase();
  if (!auth.currentUser) { const error = new Error('A sessão terminou. Inicie sessão novamente.'); error.status = 401; throw error; }
  return auth.currentUser.getIdToken(force);
}
