/* Service worker de Agencieros (PWA, 10/11/2026).
   Modo básico sin conexión, SIN guardar datos privados:
   - Archivos estáticos propios (css, js, íconos, imágenes) -> se guardan y se
     actualizan en segundo plano, así la app abre rápido y sin pantalla rota.
   - Páginas (navegación) -> siempre de la red; si no hay conexión se muestra
     /static/offline.html. Nunca se guarda HTML de la app (stock, precios,
     clientes) ni fotos subidas ni respuestas de formularios. */
var VERSION = 'agencieros-v1';
var OFFLINE = '/static/offline.html';

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(VERSION).then(function (c) { return c.addAll([OFFLINE]); }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (ks) {
    return Promise.all(ks.filter(function (k) { return k !== VERSION; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

function esEstatico(url) {
  return url.origin === self.location.origin && url.pathname.indexOf('/static/') === 0
    && url.pathname.indexOf('/static/uploads/') !== 0 && url.pathname.indexOf('/static/video/') !== 0
    && url.pathname.indexOf('/static/demo/') !== 0;
}

self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET') return;
  var url = new URL(req.url);
  if (req.mode === 'navigate') {
    e.respondWith(fetch(req).catch(function () { return caches.match(OFFLINE); }));
    return;
  }
  if (esEstatico(url)) {
    e.respondWith(caches.open(VERSION).then(function (c) {
      return c.match(req).then(function (hit) {
        var red = fetch(req).then(function (r) { if (r && r.ok) c.put(req, r.clone()); return r; }).catch(function () { return hit; });
        return hit || red;
      });
    }));
  }
});
