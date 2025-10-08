// Service Worker for offline caching
const CACHE_NAME = 'magion-display-v1';
const MEDIA_CACHE = 'magion-media-v1';
const API_CACHE = 'magion-api-v1';

// Install event - cache core files
self.addEventListener('install', (event) => {
    console.log('Service Worker installing...');
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll([
                // Add core files here if needed
            ]);
        })
    );
    self.skipWaiting();
});

// Activate event
self.addEventListener('activate', (event) => {
    console.log('Service Worker activating...');
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME && cacheName !== MEDIA_CACHE && cacheName !== API_CACHE) {
                        console.log('Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
    return self.clients.claim();
});

// Fetch event - cache media files and API requests
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // Cache media files (images and videos)
    if (url.pathname.startsWith('/media/') ||
        url.pathname.startsWith('/optimized/') ||
        url.pathname.startsWith('/uploads/')) {

        event.respondWith(
            caches.open(MEDIA_CACHE).then((cache) => {
                return cache.match(event.request).then((cachedResponse) => {
                    // Return cached version if available
                    if (cachedResponse) {
                        console.log('Serving from cache:', url.pathname);
                        return cachedResponse;
                    }

                    // Otherwise fetch and cache
                    return fetch(event.request).then((networkResponse) => {
                        // Only cache successful responses
                        if (networkResponse && networkResponse.status === 200) {
                            cache.put(event.request, networkResponse.clone());
                        }
                        return networkResponse;
                    }).catch(() => {
                        console.log('Failed to fetch, no cache available:', url.pathname);
                        // Return a placeholder or error response
                        return new Response('Offline - media not available', {
                            status: 503,
                            statusText: 'Service Unavailable'
                        });
                    });
                });
            })
        );
    }
    // Cache external JSON API requests (e.g., halbooking.dk)
    else if (url.hostname.includes('halbooking.dk') ||
             (url.pathname.includes('.asp') && event.request.method === 'GET')) {

        event.respondWith(
            caches.open(API_CACHE).then((cache) => {
                return fetch(event.request).then((networkResponse) => {
                    // Cache successful responses
                    if (networkResponse && networkResponse.status === 200) {
                        cache.put(event.request, networkResponse.clone());
                        console.log('Cached API response:', url.href);
                    }
                    return networkResponse;
                }).catch(() => {
                    // If offline, try to serve from cache
                    return cache.match(event.request).then((cachedResponse) => {
                        if (cachedResponse) {
                            console.log('Serving API from cache (offline):', url.href);
                            return cachedResponse;
                        }
                        // No cache available
                        return new Response(JSON.stringify({
                            error: 'Offline',
                            message: 'API ikke tilgængelig offline og ingen cached data'
                        }), {
                            status: 503,
                            statusText: 'Service Unavailable',
                            headers: { 'Content-Type': 'application/json' }
                        });
                    });
                });
            })
        );
    }
    // For other requests, use network-first with cache fallback
    else {
        event.respondWith(
            fetch(event.request).catch(() => {
                // If offline, try cache
                return caches.match(event.request);
            })
        );
    }
});

// Listen for messages from main thread
self.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'CLEAR_CACHE') {
        event.waitUntil(
            caches.keys().then((cacheNames) => {
                return Promise.all(
                    cacheNames.map((cacheName) => {
                        return caches.delete(cacheName);
                    })
                );
            })
        );
    }
});
