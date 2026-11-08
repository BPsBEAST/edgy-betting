// Keep public sports data live: never persist odds, schedules or analyses offline.
const SHELL_CACHE="edgy-betting-shell-v3";
const SHELL=["./","./index.html","./styles.css","./app.js","./src/engine.js","./src/radar.js","./assets/edgy-mark.svg"];
self.addEventListener("install",event=>{event.waitUntil(caches.open(SHELL_CACHE).then(cache=>cache.addAll(SHELL)).then(()=>self.skipWaiting()))});
self.addEventListener("activate",event=>{event.waitUntil(Promise.all([caches.keys().then(keys=>Promise.all(keys.filter(key=>key!==SHELL_CACHE).map(key=>caches.delete(key)))),self.clients.claim()]))});
self.addEventListener("fetch",event=>{
 const request=event.request;
 if(request.method!=="GET")return;
 const url=new URL(request.url);
 if(url.origin!==self.location.origin)return;
 if(url.pathname.includes("/data/"))return; // never serve stale odds or results
 event.respondWith(fetch(request).then(response=>{
  if(response.ok){const copy=response.clone();caches.open(SHELL_CACHE).then(cache=>cache.put(request,copy)).catch(()=>{});}
  return response;
 }).catch(()=>caches.match(request)));
});
