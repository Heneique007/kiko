import { config } from './config.js';

const BUILD = document.querySelector('meta[name="kiko-build"]').content;
const DEFAULT = document.querySelector('meta[name="kiko-version"]').content;
const scope = new URL('./', document.baseURI).href;
const prefix = `kiko-static-${encodeURIComponent(scope)}-`;
const key = `kiko-release:${scope}`;
const attemptKey = `${key}:attempt`;
const valid = value => value && typeof value.version === 'string' && /^[A-Za-z0-9][A-Za-z0-9._+-]{0,39}$/.test(value.version) && typeof value.build === 'string' && /^(source|[a-f0-9]{24})$/.test(value.build);
function get(name) { try { return localStorage.getItem(name); } catch { return null; } }
function put(name, value) { try { localStorage.setItem(name, value); return localStorage.getItem(name) === value; } catch { return false; } }
async function read(url) {
  try {
    const response = await fetch(url, {cache:'no-store', credentials:'omit', signal:AbortSignal.timeout(12000)});
    if (!response.ok) return null;
    const value = await response.json(); return valid(value) ? value : null;
  } catch { return null; }
}
async function clearStatic() {
  if (!('caches' in window)) return;
  for (const name of await caches.keys()) if (name.startsWith(prefix) || /^kiko-static-v\d+$/.test(name)) await caches.delete(name);
}

export function setupVersion(chat) {
  const label = document.getElementById('app-version');
  const stored = get(key);
  const previous = stored?.startsWith(`${BUILD}:`) ? stored.slice(BUILD.length + 1) : DEFAULT;
  label.textContent = previous;
  const cleanUrl = new URL(location.href);
  if (cleanUrl.searchParams.has('_kiko')) {
    cleanUrl.searchParams.delete('_kiko');
    history.replaceState(history.state, '', cleanUrl.href);
  }
  let running = false, reloading = false, registration;
  if ('serviceWorker' in navigator && (location.protocol === 'https:' || ['localhost','127.0.0.1'].includes(location.hostname))) {
    navigator.serviceWorker.register(new URL('./sw.js', scope), {scope, updateViaCache:'none'})
      .then(reg => { registration = reg; }).catch(() => {});
  }
  const safe = () => !chat.busy && !chat.turns.length && !chat.attachments.items.length && !document.getElementById('message-input').value && (document.getElementById('login-view').hidden || (!document.getElementById('email').value && !document.getElementById('password').value));
  const refresh = async (target, verified = null) => {
    if (!safe() || get(attemptKey) === target) return false;
    // One reload per target even if a CDN still serves old HTML. If storage is
    // unavailable, do not risk a reload loop.
    try { await clearStatic(); } catch { /* HTTP cache bust still works. */ }
    if (registration) registration.update().catch(() => {});
    if (!safe() || !put(attemptKey, target)) return false;
    if (verified && !put(key, verified)) return false;
    reloading = true;
    const url = new URL(location.href);
    url.searchParams.set('_kiko', `${Date.now()}`);
    location.replace(url.href);
    return true;
  };
  async function check() {
    if (running || reloading || !navigator.onLine || document.hidden) return;
    running = true;
    try {
      const api = config.apiBaseUrl ? config.apiBaseUrl.replace(/\/$/, '') + '/api/version' : null;
      // Cache bust the published manifest as well as using no-store.
      const manifest = new URL('./version.json', scope); manifest.searchParams.set('_kiko', Date.now());
      const [published, server] = await Promise.all([read(manifest), api ? read(api) : null]);
      if (published && published.build !== BUILD) {
        await refresh(`build:${published.build}`);
        return;
      }
      // Do not claim the Render version is loaded if Pages has not published
      // that build yet. A later check will detect the new Pages manifest.
      if (server && server.build !== BUILD) {
        // Render may have deployed before Pages. One cache refresh is safe;
        // do not label the old build as the new version or loop.
        await refresh(`server-build:${server.build}`);
        return;
      }
      // A temporary Render outage must not revert a previously verified version.
      const current = get(key);
      if (!server && current?.startsWith(`${BUILD}:`)) return;
      const desired = server?.version || published?.version;
      if (!desired) return;
      const target = `${BUILD}:${desired}`;
      if (current !== target) {
        if ((current?.startsWith(`${BUILD}:`) && current !== target) || (!current?.startsWith(`${BUILD}:`) && desired !== DEFAULT)) {
          if (!safe()) return;
          await refresh(`version:${target}`, target);
          return;
        }
        put(key, target);
      }
      label.textContent = desired;
    } finally { running = false; }
  }
  check().catch(() => {});
  const trigger = () => check().catch(() => {});
  window.addEventListener('online', trigger);
  window.addEventListener('focus', trigger);
  window.addEventListener('pageshow', trigger);
  document.addEventListener('visibilitychange', trigger);
  document.getElementById('new-chat').addEventListener('click', trigger);
  setInterval(trigger, 60000);
}
