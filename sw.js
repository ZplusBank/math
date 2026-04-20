const CACHE_VERSION = 'zplus-math-cache-v1';
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const RUNTIME_CACHE = `${CACHE_VERSION}-runtime`;

const PRECACHE_URLS = [
    './',
    './index.html',
    './css/exam-styles.css',
    './css/styles-append.css',
    './js/lib-loader.js',
    './js/exam-config.js',
    './js/content-renderer.js',
    './js/diagram-handler.js',
    './js/exam-engine.js',
    './js/floating-lines.js',
    './favicon.ico'
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(STATIC_CACHE).then((cache) => cache.addAll(PRECACHE_URLS)).then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) => Promise.all(
            keys.filter((key) => key.startsWith('zplus-math-cache-') && key !== STATIC_CACHE && key !== RUNTIME_CACHE)
                .map((key) => caches.delete(key))
        )).then(() => self.clients.claim())
    );
});

function isCacheableRequest(request) {
    return request.method === 'GET' && new URL(request.url).origin === self.location.origin;
}

self.addEventListener('fetch', (event) => {
    const { request } = event;
    if (!isCacheableRequest(request)) return;

    const url = new URL(request.url);

    if (request.mode === 'navigate') {
        event.respondWith((async () => {
            try {
                const networkResponse = await fetch(request);
                const cache = await caches.open(STATIC_CACHE);
                cache.put('./index.html', networkResponse.clone());
                return networkResponse;
            } catch (error) {
                const cached = await caches.match('./index.html');
                if (cached) return cached;
                throw error;
            }
        })());
        return;
    }

    const isRuntimeData = url.pathname.endsWith('.json') || url.pathname.includes('/data/');
    const strategy = isRuntimeData ? 'network-first' : 'stale-while-revalidate';

    event.respondWith((async () => {
        const cache = await caches.open(RUNTIME_CACHE);
        const cached = await cache.match(request);

        if (strategy === 'stale-while-revalidate') {
            const networkPromise = fetch(request).then((response) => {
                if (response && response.ok) {
                    cache.put(request, response.clone());
                }
                return response;
            }).catch(() => null);

            if (cached) {
                event.waitUntil(networkPromise);
                return cached;
            }

            const networkResponse = await networkPromise;
            if (networkResponse) return networkResponse;
            return cached || Response.error();
        }

        try {
            const networkResponse = await fetch(request);
            if (networkResponse && networkResponse.ok) {
                cache.put(request, networkResponse.clone());
            }
            return networkResponse;
        } catch (error) {
            if (cached) return cached;
            throw error;
        }
    })());
});
