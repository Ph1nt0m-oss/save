self.addEventListener('install', (e) => {
    e.waitUntil(
        caches.open('shopping-list-cache').then((cache) => cache.addAll([
            './',
            './index.html',
            './App.jsx',
            './styles.css'
        ]))
    );
});

self.addEventListener('fetch', (e) => {
    e.respondWith(
        caches.match(e.request).then((response) => response || fetch(e.request))
    );
});