/* v0.23 FareAlert service worker: offline shell.
   /static/* cache-first (URLs carry ?v= busting); /api/* GET network-first
   with cache fallback so the last data stays readable offline. */
var CACHE = "fare-alert-v22";

self.addEventListener("install", function () {
  self.skipWaiting();
});

self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) {
      return k !== CACHE;
    }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener("fetch", function (e) {
  if (e.request.method !== "GET") return;
  var url = new URL(e.request.url);
  if (url.origin !== self.location.origin) return;

  function cachePut(req, resp) {
    var clone = resp.clone();
    caches.open(CACHE).then(function (c) {
      return c.put(req, clone);
    }).catch(function () {});  // quota etc: never break the live response
  }

  if (url.pathname.indexOf("/api/") === 0) {
    e.respondWith(fetch(e.request).then(function (r) {
      if (r && r.ok) cachePut(e.request, r);
      return r;
    }).catch(function () {
      return caches.match(e.request).then(function (m) {
        return m || new Response(
          JSON.stringify({ ok: false, error: "离线:接口无缓存副本" }),
          { status: 503, headers: { "Content-Type": "application/json" } });
      });
    }));
    return;
  }

  if (url.pathname.indexOf("/static/") === 0) {
    e.respondWith(caches.match(e.request).then(function (m) {
      return m || fetch(e.request).then(function (r) {
        if (r && r.ok) cachePut(e.request, r);
        return r;
      });
    }));
  }

  if (e.request.mode === "navigate") {
    // network-first keeps ?v= refs fresh; cached copy lets the UI cold-start
    // offline (the /api fallback then serves the last seen data)
    e.respondWith(fetch(e.request).then(function (r) {
      if (r && r.ok) cachePut(e.request, r);
      return r;
    }).catch(function () {
      return caches.match(e.request).then(function (m) {
        return m || new Response("离线且无缓存副本,恢复网络后刷新即可。",
          { status: 503, headers: { "Content-Type": "text/plain; charset=utf-8" } });
      });
    }));
  }
});
