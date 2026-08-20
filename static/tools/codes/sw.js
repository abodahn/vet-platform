/* Service worker for the licence code tool. Scope: /static/tools/codes/
 *
 * WHY THIS ONE CACHES PAGES WHEN static/sw.js DELIBERATELY DOES NOT
 *
 * The app's service worker refuses to cache any page, for two reasons it spells
 * out: a cached HTML page is a stale medical record, and the cache is shared by
 * every account on a reception desktop. Both are right, and neither applies here:
 *
 *   - This page holds no clinical data. It is a calculator. There is nothing
 *     to go stale - the same inputs give the same code today and in five years.
 *   - It is not behind a login and there is nothing account-specific in it.
 *     The master secret lives in localStorage, which a service worker cache
 *     cannot reach and never touches.
 *   - Working with no signal is the entire point. A clinic phones at 8pm from
 *     somewhere with no coverage; a tool that needs the network to load is
 *     useless exactly when it is needed.
 *
 * So this one caches aggressively and on purpose, in its own scope, where it
 * cannot affect a single page of the application.
 *
 * Cache-first, with a background refresh. The tool must open instantly and
 * offline; a new version lands on the visit after it is published, which for a
 * calculator that has not changed in months is the right trade.
 */
const CACHE = "aleefy-codes-v2";
const ASSETS = [
  "./",
  "./index.html",
  "./manifest.json",
  "/static/images/tool-icon-192.png",
  "/static/images/tool-icon-512.png",
  "/static/images/tool-icon-apple.png",
];

self.addEventListener("install", (e) => {
  // addAll fails the whole install if any one entry 404s, which would leave the
  // tool with no offline copy at all. Each is added on its own so a missing
  // icon cannot cost us the page itself.
  e.waitUntil(
    caches.open(CACHE)
      .then((c) => Promise.all(ASSETS.map((u) => c.add(u).catch(() => null))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => k.startsWith("aleefy-codes-") && k !== CACHE)
            .map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;

  e.respondWith(
    caches.match(req).then((hit) => {
      // Refresh in the background so a republish is picked up next time, but
      // never make the user wait for the network to see the tool.
      const fresh = fetch(req)
        .then((res) => {
          if (res && res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(req, copy));
          }
          return res;
        })
        .catch(() => hit);        // offline: whatever we already hold

      return hit || fresh;
    })
  );
});
