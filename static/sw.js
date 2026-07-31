/* Service worker — the minimum that makes the app installable.
 *
 * It caches STATIC ASSETS ONLY. Never a page, never an API response, never
 * anything behind the login. That restraint is the whole design:
 *
 *   - A cached HTML page is a stale medical record. Serving a vet yesterday's
 *     weight, yesterday's dose or yesterday's allergy list from a cache the
 *     user cannot see is worse than showing nothing at all.
 *   - The cache is shared by every account on the device. Caching an
 *     authenticated page would leak one user's patients to the next person who
 *     logs in on the reception desktop.
 *
 * So: offline gets an honest "you are offline" page, not a plausible-looking
 * stale one. Real offline clinical work needs a sync layer with conflict
 * resolution, which is a product decision, not a caching trick.
 *
 * Static assets use stale-while-revalidate: instant from cache, refreshed in
 * the background, so a deploy that changes app.min.css lands on the next load
 * without anyone bumping a version constant.
 */
const CACHE = "assets-v1";

self.addEventListener("install", (e) => {
  // Take over as soon as installed rather than waiting for every tab to close.
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // Everything that is not a static asset goes straight to the network,
  // untouched — pages, APIs, uploads, exports, PDFs.
  if (!url.pathname.startsWith("/static/")) {
    if (req.mode === "navigate") {
      e.respondWith(fetch(req).catch(() => offlinePage()));
    }
    return;
  }

  e.respondWith(
    caches.open(CACHE).then((cache) =>
      cache.match(req).then((hit) => {
        const net = fetch(req)
          .then((res) => {
            // Only store a complete, successful response. An opaque or partial
            // one cached here would be served forever as if it were the asset.
            if (res.ok && res.status === 200) cache.put(req, res.clone());
            return res;
          })
          .catch(() => hit);          // offline: whatever we already had
        return hit || net;
      })
    )
  );
});

function offlinePage() {
  return new Response(
    `<!doctype html><html><head><meta charset="utf-8">
     <meta name="viewport" content="width=device-width,initial-scale=1">
     <title>Offline</title><style>
     body{font-family:system-ui,sans-serif;background:#F7F5F1;color:#1C1A17;
          display:grid;place-items:center;height:100vh;margin:0;text-align:center}
     div{max-width:22rem;padding:2rem}
     h1{font-size:1.15rem;margin:0 0 .5rem}
     p{color:#5A5246;font-size:.9rem;line-height:1.6;margin:0 0 1.5rem}
     button{background:#0B7A6B;color:#fff;border:0;border-radius:10px;
            padding:.7rem 1.4rem;font-size:.9rem;cursor:pointer}
     </style></head><body><div>
     <h1>No connection &middot; لا يوجد اتصال</h1>
     <p>This app needs the clinic network to show patient records.
        Nothing is cached on this device, so nothing here is out of date.<br><br>
        البرنامج يحتاج اتصال بالشبكة لعرض بيانات الحالات.</p>
     <button onclick="location.reload()">Retry &middot; إعادة المحاولة</button>
     </div></body></html>`,
    { status: 503, headers: { "Content-Type": "text/html; charset=utf-8" } }
  );
}
