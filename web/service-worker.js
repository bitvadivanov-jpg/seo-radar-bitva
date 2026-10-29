/* Данные загружаются из сети; офлайн-копия явно помечена для интерфейса. */
const PREFIX='seo-radar:'+new URL(self.registration.scope).pathname+':';
const VERSION=PREFIX+'v6';
const CORE=['./','./index.html','./styles.css','./app.js?v=20261029-2','./manifest.webmanifest','./icons/icon-192.png','./icons/icon-512.png'];
const dataURL=new URL('./data/positions.json',self.registration.scope).href;
self.addEventListener('install',event=>{
  event.waitUntil(caches.open(VERSION).then(cache=>cache.addAll(CORE)).then(()=>self.skipWaiting()));
});
self.addEventListener('activate',event=>{
  event.waitUntil(Promise.all([
    caches.keys().then(keys=>Promise.all(keys.filter(key=>key.startsWith(PREFIX)&&key!==VERSION).map(key=>caches.delete(key)))),
    self.clients.claim()
  ]));
});
self.addEventListener('fetch',event=>{
  const req=event.request;
  const url=new URL(req.url);
  if(req.method!=='GET'||url.origin!==self.location.origin||!url.href.startsWith(self.registration.scope))return;
  if(url.pathname===new URL(dataURL).pathname){
    event.respondWith((async()=>{
      const cache=await caches.open(VERSION);
      try{
        const response=await fetch(req,{cache:'no-store'});
        if(!response.ok)throw new Error('HTTP '+response.status);
        await cache.put(dataURL,response.clone());
        return response;
      }catch{
        const cached=await cache.match(dataURL);
        if(!cached)return new Response('{}',{status:503,headers:{'Content-Type':'application/json'}});
        const headers=new Headers(cached.headers);
        headers.set('X-SEO-Radar-Cache','offline');
        return new Response(await cached.arrayBuffer(),{status:200,headers});
      }
    })());
    return;
  }
  // Сеть сначала: новая публикация не смешивается с устаревшими HTML/JS.
  event.respondWith((async()=>{
    try{
      const response=await fetch(req);
      if(!response.ok)throw new Error('HTTP '+response.status);
      const cache=await caches.open(VERSION);
      await cache.put(req,response.clone());
      return response;
    }catch{
      return await caches.match(req,{ignoreSearch:true})||new Response('Нет сохранённой копии',{status:503});
    }
  })());
});
