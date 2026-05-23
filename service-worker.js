const BUILD_VERSION = new URL(self.location.href).searchParams.get('v') || 'local';
const CACHE_NAME = `akro-du-foot-${BUILD_VERSION}`;
const APP_SHELL = [
  '/manifest.json',
  '/icons/icon-32.png',
  '/icons/icon-64.png',
  '/icons/icon-180.png',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
  '/icons/splash-1170x2532.png',
  '/icons/splash-1290x2796.png',
  '/avatars/avatar-angry.png',
  '/avatars/avatar-arabic-wink.png',
  '/avatars/avatar-blond-sunglasses.png',
  '/avatars/avatar-blonde-girl-thumb.png',
  '/avatars/avatar-brun-classy.png',
  '/avatars/avatar-brune-cool.png',
  '/avatars/avatar-cap-happy.png',
  '/avatars/avatar-cap-whistle.png',
  '/avatars/avatar-cool.png',
  '/avatars/avatar-cry.png',
  '/avatars/avatar-kiss.png',
  '/avatars/avatar-laugh.png',
  '/avatars/avatar-love.png',
  '/avatars/avatar-mask.png',
  '/avatars/avatar-red-card.png',
  '/avatars/avatar-redhair-girl-wink.png',
  '/avatars/avatar-shush-dark.png',
  '/avatars/avatar-shush.png',
  '/avatars/avatar-yellow-card.png',
  '/avatars/avatar-trophy.png'
];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(APP_SHELL)).catch(() => null));
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key)))));
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.pathname.startsWith('/api/')) return;

  if (request.mode === 'navigate') {
    event.respondWith(fetch(request, {cache: 'no-store'}).then(response => {
      const copy = response.clone();
      caches.open(CACHE_NAME).then(cache => cache.put('/', copy)).catch(() => null);
      return response;
    }).catch(() => caches.match('/')));
    return;
  }

  event.respondWith(caches.match(request).then(cached => cached || fetch(request).then(response => {
    if (response && response.ok && url.origin === location.origin) {
      const copy = response.clone();
      caches.open(CACHE_NAME).then(cache => cache.put(request, copy)).catch(() => null);
    }
    return response;
  }).catch(() => cached)));
});
