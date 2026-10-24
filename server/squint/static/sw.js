self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (url.pathname === '/try' && e.request.method === 'GET') {
    e.respondWith(fetch(e.request).catch(() => caches.match('/try')));
  }
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.open('squint-v1').then(c => c.addAll(['/try', '/manifest.webmanifest', '/icon.svg'])).catch(() => {}));
});
