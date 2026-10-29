/* SEO-Радар. Данные Яндекс Вебмастера. Без сторонних JS-библиотек и без OAuth-токенов. */
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const escapeHTML = (value) => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const number = (v) => typeof v === 'number' && Number.isFinite(v);
  const STORAGE_KEY = 'seo-radar-last-v2:' + new URL('./', location.href).pathname;
  const formatNumber = v => number(v) ? v.toLocaleString('ru-RU', {maximumFractionDigits:0}) : '—';
  const formatRank = v => number(v) ? v.toLocaleString('ru-RU',{maximumFractionDigits:1}) : '—';
  const dateLabel = value => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value || '')) return '—';
    return new Date(value + 'T12:00:00').toLocaleDateString('ru-RU',{day:'2-digit',month:'short'});
  };
  const dateFull = value => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value || '')) return '—';
    return new Date(value + 'T12:00:00').toLocaleDateString('ru-RU');
  };
  const safeISO = value => {
    const date = new Date(value || '');
    return Number.isFinite(date.getTime()) ? date : null;
  };
  const bootstrap = (() => { try { return JSON.parse($('bootstrap').textContent) } catch {return {}} })();
  let data = {
    schema:2, site:'битвадиванов.рф', status:'not_connected', updated_at:null,
    keywords:Array.isArray(bootstrap.keywords) ? bootstrap.keywords : [], measurements:[], errors:[],
  };
  const state = {engine:'Yandex',region:'22',device:'mobile',group:'all',search:'',tab:'overview',offline:false};
  let installPrompt = null;
  let toastTimer;

  const showToast = message => {
    const t=$('toast'); t.textContent=message; t.classList.add('show');
    clearTimeout(toastTimer);toastTimer=setTimeout(()=>t.classList.remove('show'),4200);
  };
  function currentRows() {
    if(state.engine!=='Yandex') return [];
    return (Array.isArray(data.measurements)?data.measurements:[])
      .filter(r=>r&&r.region===state.region&&r.device===state.device&&typeof r.query==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(r.date||''));
  }
  function allKeywords() {
    return Array.isArray(data.keywords) ? data.keywords.filter(x=>x&&typeof x.query==='string'&&typeof x.group==='string') : [];
  }
  function getByQuery() {
    const grouped = new Map();
    for (const r of currentRows()) {
      const key = r.query.toLocaleLowerCase('ru-RU');
      if (!grouped.has(key)) grouped.set(key,[]);
      grouped.get(key).push(r);
    }
    for (const r of grouped.values()) r.sort((a,b)=>b.date.localeCompare(a.date));
    return grouped;
  }
  function currentQueryStats(query, grouped) {
    const records=grouped.get(query.toLocaleLowerCase('ru-RU'))||[];
    const latest=records[0]||null;
    const previous=records.find(r=>latest&&r.date<latest.date&&number(r.position))||null;
    const delta=latest&&number(latest.position)&&previous ? previous.position-latest.position : null;
    return {latest,previous,delta,history:records};
  }
  function deltaHTML(delta){
    if(!number(delta)) return '<span class="delta same">—</span>';
    if(Math.abs(delta)<0.05) return '<span class="delta same">0</span>';
    return delta>0?`<span class="delta up">↑ ${formatRank(delta)}</span>`:`<span class="delta down">↓ ${formatRank(Math.abs(delta))}</span>`;
  }
  function rankHTML(v){
    if(!number(v)) return '<span class="rank-value unknown">—</span>';
    const cls = v<=3?'position-3':v<=10?'position-10':'';
    return `<span class="rank-value ${cls}">${formatRank(v)}</span>`;
  }
  function emptyHTML(title,description,icon='⌁'){
    return `<div class="empty"><div class="empty-symbol">${escapeHTML(icon)}</div><strong>${escapeHTML(title)}</strong><p>${escapeHTML(description)}</p></div>`;
  }
  function dateTimeFormat(iso) {
    const date=safeISO(iso);
    return date?new Intl.DateTimeFormat('ru-RU',{timeZone:'Europe/Kaliningrad',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}).format(date):'Не было проверок';
  }
  function updateStatus(){
    const dot=$('status-dot'); const label=$('sync-status');const date=$('last-update');
    let message = 'Ожидание подключения';let css='';
    if(state.engine==='Google') {message='Google пока не подключён';}
    else if(data.status==='ok'){message='Яндекс подключён';css='ok';}
    else if(data.status==='partial'){message='Сбор с ошибками';css='error';}
    else if(data.status==='error'){message='Ошибка подключения';css='error';}
    if(state.offline) message+=' · офлайн';
    dot.className='status-dot '+css;
    label.textContent=message;
    date.textContent=dateTimeFormat(data.last_attempt_at || data.updated_at);
    const latestPositionDate=currentRows().filter(r=>number(r.position)).map(r=>r.date).sort().at(-1);
    $('last-statistic').textContent=dateFull(latestPositionDate);
    const warning=$('warning');warning.className='warning';warning.innerHTML='';
    let text=''; let neutral=false;
    if(state.engine==='Google') text='<strong>Google пока не подключён.</strong> Реальные позиции Google появятся только после подключения отдельного источника данных; переключение на Google не создаёт вымышленные показатели.';
    else if(data.status==='not_connected') text='<strong>Подключение ещё не выполнено.</strong> Список поисковых запросов готов. Для автоматического обновления нужен OAuth-токен Яндекс Вебмастера в секретах GitHub. Перейдите во вкладку «Подключение».';
    else if(data.status==='error') text='<strong>Ошибка сбора данных.</strong> '+escapeHTML(data.errors?.[0]?.message||'Проверьте токен и права на сайт.')+' Старые сохранённые измерения не удалены.';
    else if(data.status==='partial') text='<strong>Часть запросов не обновилась.</strong> Успешные измерения сохранены. Проверьте вкладку Actions в GitHub.';
    else if(data.status==='ok' && !latestPositionDate) {text='API подключён, но для выбранного региона и устройства пока нет показов с определённой позицией. Это не означает, что сайт находится за пределами ТОП-100.';neutral=true;}
    else if(data.status==='ok' && Date.now()-new Date(latestPositionDate+'T23:59:59+02:00').getTime()>72*3600000) {text='<strong>Последняя доступная статистика позиций: '+escapeHTML(dateFull(latestPositionDate))+';</strong> Яндекс пока не вернул более свежие значения. Успешная проверка подключения не означает, что статистика обновилась.';}
    else if(data.status==='ok' && data.collection && data.collection.current_position_records===0) {text='Последний сбор завершился, но новых значений позиций Яндекс не предоставил. Показана сохранённая история на указанную дату статистики.';neutral=true;}
    else if((data.last_success_at||data.updated_at) && safeISO(data.last_success_at||data.updated_at) && Date.now()-safeISO(data.last_success_at||data.updated_at).getTime() > 48*3600000){text='<strong>Сбор давно не завершался успешно.</strong> Проверьте последний запуск GitHub Actions. Позиции показаны на указанную дату статистики.';}
    if(state.offline) text='<strong>Нет подключения к сети.</strong> Показаны сохранённые данные, если они были доступны ранее. '+text;
    if(text){warning.innerHTML=text;warning.classList.add('is-visible');if(neutral)warning.classList.add('neutral')}
  }
  function updateKPIs(){
    const kw=allKeywords();const grouped=getByQuery();const stats=kw.map(k=>currentQueryStats(k.query,grouped));
    const visible=stats.filter(s=>number(s.latest?.position));
    const top10=visible.filter(s=>s.latest.position<=10).length;
    const top3=visible.filter(s=>s.latest.position<=3).length;
    const losses=stats.filter(s=>number(s.delta)&&s.delta<=-3).length;
    const cards=[
      ['Отслеживаемые фразы',kw.length,'Задано для ежедневной проверки','⌕'],
      ['С позицией',visible.length,'Для региона и устройства','◉'],
      ['В ТОП-10',visible.length?top10:'—',visible.length?`Из них в ТОП-3: ${top3}`:'Ожидаются замеры','↗'],
      ['Падение на 3+ места',visible.length?losses:'—',visible.length?'Сравнение дат':'Нужно два периода','↘'],
    ];
    $('kpis').innerHTML=cards.map(([name,value,foot,icon])=>`<article class="kpi"><div class="kpi-top"><span>${name}</span><span class="kpi-icon">${icon}</span></div><strong>${value}</strong><small>${foot}</small></article>`).join('');
  }
  function buildChart(){
    const rows=currentRows().filter(r=>number(r.position));
    const groups=new Map();
    for(const r of rows){
      if(!groups.has(r.date)) groups.set(r.date,[]);
      groups.get(r.date).push(r.position);
    }
    const points=[...groups.entries()].sort(([a],[b])=>a.localeCompare(b)).map(([date,values])=>({date,rank:values.reduce((a,b)=>a+b,0)/values.length,count:values.length}));
    const chart=$('chart');
    if(points.length<2){chart.innerHTML=emptyHTML('График появится после проверок','Нужны реальные позиции минимум за два разных дня. Сейчас нет достаточной истории.');return;}
    const W=650,H=230,L=44,R=18,T=22,B=33;
    const vals=points.map(p=>p.rank),min=Math.max(1,Math.floor(Math.min(...vals)-1.5)),max=Math.ceil(Math.max(...vals)+1.5),span=Math.max(1,max-min);
    const xy=(p,i)=>({x:L+i*(W-L-R)/(points.length-1),y:T+(p.rank-min)*(H-T-B)/span});
    const vec=points.map(xy);
    const path=vec.map((p,i)=>`${i?'L':'M'}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
    const grid=[0,.25,.5,.75,1].map(t=>{const yy=T+t*(H-T-B);const val=min+t*span;return `<line x1="${L}" y1="${yy}" x2="${W-R}" y2="${yy}" stroke="#304052" stroke-dasharray="4 5"/><text x="${L-11}" y="${yy+4}" text-anchor="end" font-size="11" fill="#90a4b9">${formatRank(val)}</text>`}).join('');
    const dots=vec.map((p,i)=>`<circle cx="${p.x}" cy="${p.y}" r="4.3" fill="#ff9a5c" stroke="#15212f" stroke-width="2"><title>${dateFull(points[i].date)} — ${formatRank(points[i].rank)}</title></circle>`).join('');
    chart.innerHTML=`<div style="width:100%"><svg class="chart-svg" viewBox="0 0 ${W} ${H}" aria-label="График средних поисковых позиций"><g>${grid}</g><path d="${path}" stroke="#ff994d" stroke-width="3.2" stroke-linecap="round" fill="none" stroke-linejoin="round"/>${dots}<text x="${L}" y="${H-5}" fill="#8598ab" font-size="11">${dateLabel(points[0].date)}</text><text x="${W-R}" y="${H-5}" fill="#8598ab" font-size="11" text-anchor="end">${dateLabel(points.at(-1).date)}</text></svg><div class="chart-foot">Чем ниже числовая позиция, тем выше сайт в выдаче. Состав запросов с данными может меняться.</div></div>`;
  }
  function updateAlerts(){
    const grouped=getByQuery();const alerts=[];
    const hasComparison=allKeywords().some(kw=>number(currentQueryStats(kw.query,grouped).delta));
    for (const kw of allKeywords()) {
      const s=currentQueryStats(kw.query,grouped);
      if(!number(s.delta)||!number(s.latest?.position)||!number(s.previous?.position)) continue;
      if(s.delta<=-3 || (s.latest.position<=10 && s.previous.position>10)) alerts.push({kw,stats:s});
    }
    alerts.sort((a,b)=>a.stats.delta-b.stats.delta);
    const el=$('alerts');
    if(!hasComparison){el.innerHTML=emptyHTML('Недостаточно данных для сравнения','Изменения появятся после получения позиций за два разных дня.','◉');return;}
    if(!alerts.length){el.innerHTML=emptyHTML('Критичных изменений нет','Если запрос снизится на 3+ места или войдёт в ТОП-10, он появится здесь.','◉');return;}
    el.innerHTML='<div class="alert-list">'+alerts.slice(0,7).map(({kw,stats})=>`<div class="alert-item"><div><b>${escapeHTML(kw.query)}</b><small>${escapeHTML(kw.group)} · ${dateLabel(stats.latest.date)}</small></div>${deltaHTML(stats.delta)}</div>`).join('')+'</div>';
  }
  function tableRow(kw,stats,compact){
    const latest=stats.latest;
    const tdList=compact ? [
      `<td><span class="query-title">${escapeHTML(kw.query)}</span><span class="query-group">${escapeHTML(kw.group)}</span></td>`,
      `<td>${rankHTML(latest?.position)}</td>`,
      `<td>${deltaHTML(stats.delta)}</td>`,
      `<td>${formatNumber(latest?.impressions)}</td>`
    ] : [
      `<td><span class="query-title">${escapeHTML(kw.query)}</span><span class="query-group">${escapeHTML(kw.group)}</span></td>`,
      `<td>${rankHTML(latest?.position)}</td>`,
      `<td>${deltaHTML(stats.delta)}</td>`,
      `<td>${formatNumber(latest?.impressions)}</td>`,
      `<td>${formatNumber(latest?.clicks)}</td>`,
      `<td>${dateLabel(latest?.date)}</td>`
    ];
    return `<tr class="clickable" tabindex="0" role="button" data-query="${escapeHTML(kw.query)}" title="Открыть историю запроса">${tdList.join('')}</tr>`;
  }
  function bindQueryClicks(parent){
    parent.querySelectorAll('tr[data-query]').forEach(el=>{
      const cb=()=>openQuery(el.dataset.query);
      el.addEventListener('click',cb);
      el.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();cb()}});
    });
  }
  function updateTables(){
    const grouped=getByQuery();const keywords=allKeywords();
    $('overview-rows').innerHTML=keywords.slice(0,10).map(k=>tableRow(k,currentQueryStats(k.query,grouped),true)).join('')||'<tr><td colspan="4">Нет запросов</td></tr>';
    bindQueryClicks($('overview-rows'));
    const groups=[...new Set(keywords.map(k=>k.group))].sort((a,b)=>a.localeCompare(b,'ru'));
    const category=$('group-select');const current=state.group;
    category.innerHTML='<option value="all">Все категории</option>'+groups.map(g=>`<option value="${escapeHTML(g)}">${escapeHTML(g)}</option>`).join('');
    category.value=groups.includes(current)?current:'all';
    const shown=keywords.filter(k=>(state.group==='all'||k.group===state.group)&&k.query.toLocaleLowerCase('ru-RU').includes(state.search.toLocaleLowerCase('ru-RU')));
    $('query-counter').textContent=shown.length+' из '+keywords.length+' запросов';
    $('keyword-rows').innerHTML=shown.length?shown.map(k=>tableRow(k,currentQueryStats(k.query,grouped),false)).join(''):'<tr><td colspan="6">Ничего не найдено</td></tr>';
    bindQueryClicks($('keyword-rows'));
    const rows=currentRows().sort((a,b)=>b.date.localeCompare(a.date)||a.query.localeCompare(b.query,'ru')).slice(0,240);
    $('history-rows').innerHTML=rows.length?rows.map(r=>`<tr><td>${dateFull(r.date)}</td><td><span class="query-title">${escapeHTML(r.query)}</span></td><td>${rankHTML(r.position)}</td><td>${formatNumber(r.impressions)}</td><td>${formatNumber(r.clicks)}</td></tr>`).join(''):'<tr><td colspan="5">Замеров пока нет</td></tr>';
  }
  function openQuery(query){
    const grouped=getByQuery();const stats=currentQueryStats(query,grouped);
    const group=allKeywords().find(k=>k.query===query)?.group||'Поисковый запрос';
    const history=stats.history;
    $('detail-content').innerHTML=`<div class="detail-label">${escapeHTML(group)} · ${state.region==='22'?'Калининград':'Калининградская область'} · ${state.device==='mobile'?'телефон':'компьютер'}</div><h2>${escapeHTML(query)}</h2><div class="detail-data"><div class="detail-chip"><span>Позиция</span><strong>${formatRank(stats.latest?.position)}</strong></div><div class="detail-chip"><span>Показы</span><strong>${formatNumber(stats.latest?.impressions)}</strong></div><div class="detail-chip"><span>Клики</span><strong>${formatNumber(stats.latest?.clicks)}</strong></div></div><p>Позиция — средняя по фактическим показам. «—» означает, что Яндекс не предоставил значения за эту дату.</p><div class="detail-label">ИСТОРИЯ ПО ДНЯМ</div><div class="table-scroll detail-history"><table><thead><tr><th>ДАТА</th><th>ПОЗИЦИЯ</th><th>ПОКАЗЫ</th><th>КЛИКИ</th></tr></thead><tbody>${history.length?history.map(r=>`<tr><td>${dateFull(r.date)}</td><td>${formatRank(r.position)}</td><td>${formatNumber(r.impressions)}</td><td>${formatNumber(r.clicks)}</td></tr>`).join(''):'<tr><td colspan="4">Данных нет</td></tr>'}</tbody></table></div>`;
    const dialog=$('detail-dialog');if(typeof dialog.showModal==='function') dialog.showModal();else showToast('Диалог поддерживается современными браузерами Android');
  }
  function render(){
    updateStatus();updateKPIs();buildChart();updateAlerts();updateTables();
  }
  function setTab(tab){
    state.tab=tab;
    for(const section of ['overview','keywords','history','settings']) $(section).classList.toggle('is-hidden',tab!==section);
    document.querySelectorAll('[data-tab]').forEach(b=>{
      const current=b.dataset.tab===tab;b.classList.toggle('is-current',current);b.setAttribute('aria-current',current?'page':'false');
    });
    $('filters').classList.toggle('is-hidden',tab==='settings');
    $('crumb').textContent={overview:'ОБЗОР',keywords:'ЗАПРОСЫ',history:'ИСТОРИЯ',settings:'ПОДКЛЮЧЕНИЕ'}[tab];
    $('page-title').innerHTML={overview:'Поисковые позиции <em>сайта</em>',keywords:'Поисковые <em>запросы</em>',history:'История <em>проверок</em>',settings:'Подключение <em>Яндекса</em>'}[tab];
    $('page-description').textContent={overview:'Позиции в Яндексе, динамика и приоритетные запросы для «Битвы диванов».',keywords:'Контроль коммерческих поисковых фраз по Калининграду и области.',history:'Как менялись позиции сайта по датам и запросам.',settings:'Инструкция по включению ежедневной проверки позиций.'}[tab];
    window.scrollTo({top:0,behavior:'instant'});
    updateStatus();
  }
  async function refresh(silent=false){
    if(location.protocol==='file:'||location.protocol==='about:'){
      state.offline=false; render();
      if(!silent)showToast('Для реального обновления опубликуйте приложение на HTTPS и подключите Яндекс API.');
      return;
    }
    const button=$('refresh-button');button.disabled=true;
    if(!silent)showToast('Загружаю опубликованные результаты проверок…');
    try{
      const response=await fetch('./data/positions.json?fresh='+Date.now(),{cache:'no-store'});
      if(!response.ok) throw new Error('HTTP '+response.status);
      const result=await response.json();
      if(result.schema!==2||!Array.isArray(result.measurements)||!Array.isArray(result.keywords)) throw new Error('Некорректный формат данных');
      data=result;state.offline=response.headers.get('X-SEO-Radar-Cache')==='offline';
      try{localStorage.setItem(STORAGE_KEY,JSON.stringify(data))}catch{}
      if(!silent)showToast(state.offline?'Сеть недоступна. Показана сохранённая копия.':'Данные загружены. Автоматические новые замеры создаёт GitHub Actions.');
    }catch(e){
      state.offline=true;
      try{
        const cached=JSON.parse(localStorage.getItem(STORAGE_KEY)||'null');
        if(cached?.schema===2 && Array.isArray(cached?.measurements)&&Array.isArray(cached?.keywords))data=cached;
      }catch{}
      if(!silent)showToast('Не удалось обновить: '+e.message+'. Проверьте интернет и публикацию.');
    }finally{button.disabled=false;render()}
  }
  function csvExport(){
    const rows=currentRows().sort((a,b)=>a.date.localeCompare(b.date));
    if(!rows.length){showToast('Пока нет реальных измерений для выгрузки');return;}
    const csvCell=s=>'"'+String(s??'').replaceAll('"','""')+'"';
    const lines=[['date','query','engine','region','device','average_position','impressions','clicks','url'].map(csvCell).join(';')];
    for (const r of rows) lines.push([r.date,r.query,'Yandex',r.region,r.device,r.position??'',r.impressions??'',r.clicks??'',r.url??''].map(csvCell).join(';'));
    const objectURL=URL.createObjectURL(new Blob(['\ufeff',lines.join('\r\n')],{type:'text/csv;charset=utf-8'}));
    const link=document.createElement('a');link.href=objectURL;link.download='bitva_divanov_seo_'+new Date().toISOString().slice(0,10)+'.csv';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(objectURL),3000);
  }
  document.querySelectorAll('[data-tab]').forEach(el=>el.onclick=()=>setTab(el.dataset.tab));
  $('all-keywords-button').onclick=()=>setTab('keywords');
  $('refresh-button').onclick=()=>refresh();
  $('engine').onchange=e=>{state.engine=e.target.value;render()};
  $('region').onchange=e=>{state.region=e.target.value;render()};
  $('device').onchange=e=>{state.device=e.target.value;render()};
  $('query-search').oninput=e=>{state.search=e.target.value;updateTables()};
  $('group-select').onchange=e=>{state.group=e.target.value;updateTables()};
  $('csv-button').onclick=csvExport;
  $('install-button').onclick=async()=>{
    if(installPrompt){installPrompt.prompt();await installPrompt.userChoice;installPrompt=null;return;}
    if(location.protocol==='file:')showToast('Для установки как приложения сначала нужна публикация на GitHub Pages (HTTPS).');
    else showToast('Chrome → меню ⋮ → Установить приложение или Добавить на главный экран.');
  };
  window.addEventListener('beforeinstallprompt',e=>{e.preventDefault();installPrompt=e});
  window.addEventListener('appinstalled',()=>showToast('SEO-Радар добавлен на устройство'));
  if('serviceWorker' in navigator && (location.protocol==='https:'||location.hostname==='localhost')){
    window.addEventListener('load',()=>navigator.serviceWorker.register('./service-worker.js').catch(()=>{}));
  }
  render();refresh(true);
})();
