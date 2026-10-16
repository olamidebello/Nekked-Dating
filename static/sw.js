const CACHE='nekked-shell-v4';
self.addEventListener('install',e=>{self.skipWaiting();e.waitUntil(caches.open(CACHE).then(c=>c.addAll(['/logo.png'])));});
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
// Only the public logo is cached. Account pages, requests and API responses stay on the network.
self.addEventListener('fetch',e=>{if(e.request.method==='GET'&&new URL(e.request.url).origin===self.location.origin&&new URL(e.request.url).pathname==='/logo.png')e.respondWith(fetch(e.request).catch(()=>caches.match('/logo.png')));});
