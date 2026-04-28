/* CodeForge AI – cache-first service worker for offline support */
/* eslint-env serviceworker */

const CACHE_VERSION = 'codeforge-v1';
const STATIC_ASSETS = ['/', '/index.html', '/manifest.json', '/favicon.ico'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE_VERSION)
      .then((cache) => cache.addAll(STATIC_ASSETS))
      .catch(() => null)
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  );
});

/**
 * Network-first for /api/*, cache-first for static assets.
 * Avoids caching POST/PUT/DELETE and bypasses /api/auth.
 */
self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);

  // Skip cross-origin (Emergent auth, GitHub, etc.)
  if (url.origin !== self.location.origin) return;

  // API: network-first, fallback to cache
  if (url.pathname.startsWith('/api/')) {
    if (url.pathname.startsWith('/api/auth')) return; // never cache auth
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(CACHE_VERSION).then((c) => c.put(req, copy));
          }
          return res;
        })
        .catch(() => caches.match(req))
    );
    return;
  }

  // Static assets: cache-first, fallback to network
  event.respondWith(
    caches.match(req).then(
      (cached) =>
        cached ||
        fetch(req).then((res) => {
          if (res.ok && (req.destination === 'script' || req.destination === 'style' || req.destination === 'image')) {
            const copy = res.clone();
            caches.open(CACHE_VERSION).then((c) => c.put(req, copy));
          }
          return res;
        })
    )
  );
});
