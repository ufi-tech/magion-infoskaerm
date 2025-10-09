// Service Worker for offline caching
const CACHE_NAME = 'magion-display-v3';
const MEDIA_CACHE = 'magion-media-v3';
const API_CACHE = 'magion-api-v3';

// Cache limits
const MAX_CACHE_SIZE = 100 * 1024 * 1024; // 100 MB
const MAX_CACHE_ITEMS = 100; // Max 100 files

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
                            cache.put(event.request, networkResponse.clone()).then(() => {
                                // Check cache limits after adding new item
                                enforceCacheLimit(MEDIA_CACHE);
                            });
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

// Cache management functions
async function getCacheSize(cacheName) {
    const cache = await caches.open(cacheName);
    const keys = await cache.keys();
    let totalSize = 0;

    for (const request of keys) {
        const response = await cache.match(request);
        if (response) {
            const blob = await response.blob();
            totalSize += blob.size;
        }
    }

    return { size: totalSize, count: keys.length };
}

async function cleanupOldCache(cacheName, currentMediaList) {
    const cache = await caches.open(cacheName);
    const keys = await cache.keys();

    // Get list of current media URLs
    const currentUrls = new Set(currentMediaList.map(m => m.path));

    let deletedCount = 0;
    for (const request of keys) {
        const url = new URL(request.url);
        const path = url.pathname;

        // Check if this cached file is still in the media list
        if (!currentUrls.has(path)) {
            await cache.delete(request);
            deletedCount++;
            console.log('Deleted old cached file:', path);
        }
    }

    return deletedCount;
}

async function enforceCacheLimit(cacheName) {
    const cache = await caches.open(cacheName);
    const keys = await cache.keys();

    // Check item count
    if (keys.length > MAX_CACHE_ITEMS) {
        const toDelete = keys.length - MAX_CACHE_ITEMS;
        console.log(`Cache limit exceeded. Deleting ${toDelete} oldest items`);

        // Delete oldest items (FIFO)
        for (let i = 0; i < toDelete; i++) {
            await cache.delete(keys[i]);
        }
    }

    // Check total size
    const { size } = await getCacheSize(cacheName);
    if (size > MAX_CACHE_SIZE) {
        console.log(`Cache size limit exceeded: ${(size / 1024 / 1024).toFixed(1)} MB`);

        // Delete oldest items until under limit
        const updatedKeys = await cache.keys();
        let currentSize = size;
        let i = 0;

        while (currentSize > MAX_CACHE_SIZE && i < updatedKeys.length) {
            const response = await cache.match(updatedKeys[i]);
            if (response) {
                const blob = await response.blob();
                currentSize -= blob.size;
                await cache.delete(updatedKeys[i]);
                console.log('Deleted for size limit:', updatedKeys[i].url);
            }
            i++;
        }
    }
}

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

    if (event.data && event.data.type === 'CLEANUP_OLD_CACHE') {
        event.waitUntil(
            cleanupOldCache(MEDIA_CACHE, event.data.mediaList).then((deletedCount) => {
                // Send response back
                event.ports[0].postMessage({
                    type: 'CLEANUP_COMPLETE',
                    deletedCount: deletedCount
                });
            })
        );
    }

    if (event.data && event.data.type === 'GET_CACHE_STATUS') {
        event.waitUntil(
            Promise.all([
                getCacheSize(MEDIA_CACHE),
                getCacheSize(API_CACHE),
                getCacheSize(CACHE_NAME)
            ]).then(([media, api, main]) => {
                event.ports[0].postMessage({
                    type: 'CACHE_STATUS',
                    media: media,
                    api: api,
                    main: main,
                    total: {
                        size: media.size + api.size + main.size,
                        count: media.count + api.count + main.count
                    }
                });
            })
        );
    }
});
