const CACHE = 'kiko-static-v2';
const STATIC = [ './', './index.html', './manifest.webmanifest', './css/variables.css', './css/style.css', './css/components.css', './css/responsive.css', './js/config.js', './js/firebase.js', './js/auth.js', './js/api.js', './js/sse.js', './js/chat.js', './js/files.js', './js/ui.js', './js/app.js', './js/vendor/marked.esm.js', './js/vendor/purify.es.mjs', './assets/wordmark.png', './assets/icons/favicon.png', './assets/icons/apple-touch-icon.png', './assets/icons/icon-192.png', './assets/icons/icon-512.png', './assets/icons/maskable-512.png' ];
const allowed = new Set(STATIC.map(path => new URL(path, self.location).href));
self.addEventListener('install', event => { event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(STATIC))); self.skipWaiting(); });
self.addEventListener('activate', event => { event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('kiko-static-') && key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim())); });
self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  // An explicit static whitelist; never API, Firebase, tokens, conversations, or attachments.
  if (request.method !== 'GET' || url.origin !== self.location.origin || !allowed.has(url.href) || request.headers.has('authorization')) return;
  event.respondWith(fetch(request).then(response => {
    if (response.ok && response.type === 'basic') { const copy = response.clone(); event.waitUntil(caches.open(CACHE).then(cache => cache.put(request, copy))); }
    return response;
  }).catch(async () => (await caches.match(request)) || Response.error()));
});
