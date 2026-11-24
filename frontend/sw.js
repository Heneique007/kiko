const BUILD = 'source';
// Scope the cache to this PWA, not to other apps on the same Pages origin.
const PREFIX = `kiko-static-${encodeURIComponent(self.registration.scope)}-`;
const CACHE = PREFIX + BUILD;
const LEGACY = /^kiko-static-v\d+$/;
const STATIC = [ './', './index.html', './manifest.webmanifest', './css/variables.css', './css/style.css', './css/components.css', './css/responsive.css', './js/config.js', './js/firebase.js', './js/auth.js', './js/api.js', './js/sse.js', './js/chat.js', './js/files.js', './js/ui.js', './js/app.js', './js/version.js', './js/vendor/marked.esm.js', './js/vendor/purify.es.mjs', './assets/wordmark.png', './assets/icons/favicon.png', './assets/icons/apple-touch-icon.png', './assets/icons/icon-192.png', './assets/icons/icon-512.png', './assets/icons/maskable-512.png' ];
const allowed = new Set(STATIC.map(path => new URL(path, self.registration.scope).href));
self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    await cache.addAll(STATIC.map(path => new Request(new URL(path, self.registration.scope), {cache:'reload'})));
    await self.skipWaiting();
  })());
});
self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) if ((key.startsWith(PREFIX) || LEGACY.test(key)) && key !== CACHE) await caches.delete(key);
    await self.clients.claim();
  })());
});
self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  // Never intercept API/version.json, Firebase, tokens, conversations or attachments.
  if (request.method !== 'GET' || url.origin !== self.location.origin || !allowed.has(url.href) || request.headers.has('authorization')) return;
  event.respondWith((async () => {
    try {
      const response = await fetch(request, {cache:'no-store'});
      if (response.ok && response.type === 'basic') {
        try { const cache = await caches.open(CACHE); await cache.put(request, response.clone()); } catch { /* Quota/storage errors do not block online use. */ }
      }
      return response;
    } catch {
      return (await (await caches.open(CACHE)).match(request)) || Response.error();
    }
  })());
});
