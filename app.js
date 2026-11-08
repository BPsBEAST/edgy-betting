import {MARKETS,evaluate} from "./src/engine.js";
import {fixtureState,isBettablePeriod,selectPreview,previewVerdict} from "./src/radar.js";
const $=id=>document.getElementById(id);
const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const safeImg=url=>typeof url==="string"&&/^https:\/\/[a-z0-9.-]+\//i.test(url)?url:"";
const localDate=d=>new Intl.DateTimeFormat("sv-SE",{timeZone:"Europe/Lisbon",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date(d));
const localTime=d=>new Intl.DateTimeFormat("pt-PT",{timeZone:"Europe/Lisbon",hour:"2-digit",minute:"2-digit"}).format(new Date(d));
const niceDate=d=>new Intl.DateTimeFormat("pt-PT",{timeZone:"Europe/Lisbon",weekday:"long",day:"numeric",month:"long"}).format(new Date(d));
const n=(v,d=1)=>Number.isFinite(v)?new Intl.NumberFormat("pt-PT",{minimumFractionDigits:d,maximumFractionDigits:d}).format(v):"—";
const readSaved=()=>{try{let list=JSON.parse(localStorage.getItem("edgy_betting_saved_v1")||"[]");return Array.isArray(list)?list.filter(x=>x&&x.matchId):[]}catch{return []}};
const state={games:[],source:"",generated:null,error:"",selected:null,filter:"upcoming",league:"all",query:"",view:"matches",saved:readSaved(),current:null,radar:"all",analysis:{models:{},generatedAt:null},odds:{matches:{},generatedAt:null},context:{contexts:{},generatedAt:null,hasApiFootballKey:false}};

async function loadIntelligence(){
 const get=async name=>{
  try{
   const response=await fetch("./data/"+name+"?v="+Date.now(),{cache:"no-store"});
   if(!response.ok)throw new Error("Feed "+name+" indisponível");
   return await response.json();
  }catch{return null;}
 };
 const [analysis,odds,context]=await Promise.all([get("analysis.json"),get("market_odds.json"),get("context.json")]);
 state.analysis=analysis&&analysis.models&&typeof analysis.models==="object"?analysis:{models:{},generatedAt:null};
 state.odds=odds&&odds.matches&&typeof odds.matches==="object"?odds:{matches:{},generatedAt:null};
 state.context=context&&context.contexts&&typeof context.contexts==="object"?context:{contexts:{},generatedAt:null,hasApiFootballKey:false};
}
function modelFor(game){return state.analysis.models?.[game?.id]||null;}
function quoteFor(game,key){return state.odds.matches?.[game?.id]?.[key]||null;}
function percentage(v){return typeof v==="number"&&Number.isFinite(v)?n(v*100,1)+"%":"—";}

const pct=x=>Number.isFinite(x)?n(x*100,1)+"%":"—";
function safeOdd(value){const x=Number(value);return Number.isFinite(x)&&x>1?n(x,2):"—";}
function statusPill(key,label){
 const styles={APOSTA:"aposta",VERIFICAR:"verificar",OBSERVAR:"observar",EXCLUIDA:"excluida",
  SEM_DADOS:"incompleto",SEM_INPLAY:"incompleto",TERMINADO:"incompleto",A_CONFIRMAR:"incompleto"};
 return '<span class="status-pill status-'+(styles[key]||"incompleto")+'">'+esc(label)+'</span>';
}
function renderRadarOverview(){
 const upcoming=state.games.filter(g=>isBettablePeriod(g));
 const finished=state.games.filter(g=>fixtureState(g).kind==="finished");
 const modeled=upcoming.filter(g=>Boolean(modelFor(g)));
 const date=state.analysis.generatedAt?niceDate(state.analysis.generatedAt)+" às "+localTime(state.analysis.generatedAt):"não disponível";
 $("radarOverview").innerHTML='<div class="radar-overview-head"><strong>'+upcoming.length+' próximos jogos</strong><span>·</span><strong>'+modeled.length+' com projeção</strong><span>·</span><strong>'+finished.length+' resultados</strong></div>'+
  '<p>As escolhas em destaque são <b>projeções estatísticas a investigar</b>, não apostas aprovadas. Falta cruzar Statarea/SportyTrader, contexto e odd Betano.</p>'+
  '<small>Fonte histórica: Football-Data.co.uk · atualização: '+esc(date)+' · '+(state.context.hasApiFootballKey?'API-Football ligada':'API-Football sem chave')+' · '+Object.values(state.context.contexts||{}).filter(x=>Boolean(x.weather)).length+' jogos com previsão meteorológica</small>';
}
function renderGamePreview(game){
 const phase=fixtureState(game),model=modelFor(game);
 if(phase.kind==="finished")return '<span class="game-preview result-preview"><strong>Resultado final: '+esc(phase.score||"por confirmar")+'</strong><small>Jogo terminado · sem tips retroativas</small></span>';
 if(phase.kind==="postponed")return '<span class="game-preview result-preview">Encontro adiado · sem análise de apostas</span>';
 if(phase.kind==="live")return '<span class="game-preview result-preview">Jogo em direto'+(phase.score?" · "+esc(phase.score):"")+' · não há modelo in-play</span>';
 if(phase.kind==="awaiting")return '<span class="game-preview result-preview">Encontro iniciado · resultado ainda não confirmado na fonte</span>';
 const info=previewVerdict(game,model,state.odds.matches?.[game.id]||{});
 if(!info.tip)return '<span class="game-preview no-data"><span>'+esc(info.reason)+'</span><span class="price-flag">SEM TIP VALIDADA</span></span>';
 const pick=info.tip,odd=info.quote?.odd;
 return '<span class="game-preview game-tip"><span class="tip-caption">PROJEÇÃO PARA INVESTIGAR</span>'+
   '<span class="tip-line"><strong>'+esc(pick.label)+'</strong><b>'+pct(pick.probability)+'</b></span>'+
   '<span class="tip-foot">Odd mínima do modelo: <b>'+safeOdd(pick.minimumOdd)+'</b>'+(odd?' · referência: '+safeOdd(odd):' · sem odd Betano')+'</span></span>';
}
function contextFor(game){return state.context.contexts?.[game?.id]||{};}
function renderContext(game){
 const data=contextFor(game),items=[];
 if(data.weather){
  const w=data.weather;
  const facts=[
   Number.isFinite(w.temperatureC)?n(w.temperatureC,0)+"°C":null,
   Number.isFinite(w.precipitationMm)?n(w.precipitationMm,1)+" mm/h chuva":null,
   Number.isFinite(w.gustKmh)?n(w.gustKmh,0)+" km/h rajadas":null
  ].filter(Boolean);
  items.push('<div class="source-evidence '+(w.alert?"source-warning":"")+'"><strong>☁ Meteorologia · Open-Meteo</strong><p>'+esc(w.city||"Cidade confirmada")+' · '+esc(facts.join(" · "))+'</p>'+
   (w.alert?'<small>⚠ Risco de chuva/vento na cidade — validar condições do relvado antes de apostar em golos.</small>':'<small>Previsão urbana: não garante o tempo no estádio.</small>')+'</div>');
 }else items.push('<div class="source-evidence missing"><strong>☁ Meteorologia</strong><p>Não há localização de estádio/cidade confirmada ou previsão horária disponível.</p></div>');
 if(data.injuries?.dataPresent){
   const players=Array.isArray(data.injuries.players)?data.injuries.players:[];
   items.push('<div class="source-evidence"><strong>✚ Lesões / castigos · API-Football</strong><p>'+players.length+' registos na fonte (a cobertura depende da liga).</p>'+
    (players.length?'<details><summary>Ver jogadores</summary>'+players.slice(0,15).map(p=>'<p>'+esc(p.team)+' — '+esc(p.name)+' · '+esc(p.type||p.reason||"Estado não indicado")+'</p>').join("")+'</details>':"")+
    '<small>Não é confirmação de ausência de outros jogadores.</small></div>');
 }else items.push('<div class="source-evidence missing"><strong>✚ Lesões / castigos</strong><p>Não recolhidos; Soccernews ainda sem integração autorizada.</p></div>');
 if(data.lineups?.confirmed&&Array.isArray(data.lineups.teams)){
    items.push('<div class="source-evidence"><strong>✓ Onzes titulares · API-Football</strong>'+
      data.lineups.teams.map(t=>'<details><summary>'+esc(t.team)+'</summary><p>'+esc((t.startingXI||[]).join(" · "))+'</p></details>').join("")+
      '<small>Serem conhecidos os onzes não significa que rotação/ausências já foram avaliadas.</small></div>');
 }else items.push('<div class="source-evidence missing"><strong>◷ Onzes confirmados</strong><p>Por verificar (normalmente são divulgados pouco antes do jogo).</p></div>');
 if(data.predictions?.probabilities){
  const p=data.predictions.probabilities;
  items.push('<div class="source-evidence"><strong>◈ Previsão independente · API-Football</strong>'+
    '<p>1: '+pct(p["1X2_H"])+' · X: '+pct(p["1X2_D"])+' · 2: '+pct(p["1X2_A"])+'</p>'+
    '<small>É uma fonte adicional identificada, não é Statarea nem SportyTrader.</small></div>');
 }else items.push('<div class="source-evidence missing"><strong>◈ Previsões independentes</strong><p>Statarea, SportyTrader e API-Football: ainda sem números confirmados para este jogo.</p></div>');
 const quoteList=Object.values(state.odds.matches?.[game?.id]||{});
 const books=new Set(quoteList.flatMap(q=>(q.quotes||[]).map(x=>x.bookmaker)));
 items.push('<div class="source-evidence '+(quoteList.length?"":"missing")+'"><strong>◎ Odds e mercado justo</strong><p>'+quoteList.length+' seleções de referência · '+books.size+' casas (API-Football, se disponível).</p><small>Betano e Flashscore não estão ligados ao boletim. Confirmar preço, mercado e hora.</small></div>');
 return '<div class="source-evidence-panel"><div class="auto-section-label">FONTES CONSULTADAS / POR VALIDAR</div>'+items.join("")+'</div>';
}

function renderWorkflowChecklist(){
 const game=state.selected;
 if(!game){$("workflowChecklist").innerHTML="";return;}
 const phase=fixtureState(game);
 if(phase.kind!=="upcoming"){
  $("workflowChecklist").innerHTML='<div class="workflow-checklist-head"><b>Estado do encontro</b>'+statusPill(phase.kind==="postponed"?"EXCLUIDA":"A_CONFIRMAR",phase.label)+'</div>'+
   '<p class="workflow-checklist-sub">As projeções pré-jogo só são apresentadas para encontros que ainda não começaram. '+(phase.score?'Resultado: '+esc(phase.score)+'.':'')+'</p>';
  return;
 }
 const info=previewVerdict(game,modelFor(game),state.odds.matches?.[game.id]||{});
 const requirements=info.requirements||[
  {label:"Histórico",ready:false,detail:"Aguarda dados suficientes"},
  {label:"Consenso 2 fontes",ready:false,detail:"Previsões por integrar"},
  {label:"Odd Betano",ready:false,detail:"Por confirmar no boletim"},
  {label:"Contexto",ready:false,detail:"Onzes e ausências por confirmar"},
  {label:"Edge ≥ 3 p.p.",ready:false,detail:"Sem odds e probabilidades cruzadas"}
 ];
 const ctx=contextFor(game);
 if(ctx.injuries?.dataPresent||ctx.weather||ctx.lineups?.confirmed){
  const item=requirements.find(x=>x.key==="context");
  if(item)item.detail="Parte do contexto já recolhida; ainda falta verificar impactos e rotação.";
 }
 const done=requirements.filter(x=>x.ready).length;
 $("workflowChecklist").innerHTML='<div class="workflow-checklist-head"><b>Critérios das tuas regras</b>'+statusPill("OBSERVAR","◉ Observar")+'</div>'+
 '<p class="workflow-checklist-sub">'+done+' de '+requirements.length+' verificações preliminares disponíveis. '+esc(info.reason)+'</p>'+
 '<div class="workflow-grid">'+requirements.map(x=>'<div class="workflow-step '+(x.ready?"ready":"waiting")+'"><span class="step-icon">'+(x.ready?"✓":"○")+'</span><div><strong>'+esc(x.label)+'</strong><small>'+esc(x.detail)+'</small></div></div>').join("")+'</div>'+
 '<div class="workflow-foot"><span>Nenhuma odd é confirmada automaticamente no boletim.</span><button type="button" data-open-manual="1">Completar análise ↗</button></div>';
}
function renderAutoPanel(){
 const game=state.selected;
 if(!game){$("autoPanel").innerHTML='<div class="auto-empty">Escolhe um jogo para veres uma seleção estatística, as probabilidades e o que falta validar.</div>';renderWorkflowChecklist();return;}
 const phase=fixtureState(game),model=modelFor(game),prices=state.odds.matches?.[game.id]||{};
 renderWorkflowChecklist();
 if(phase.kind!=="upcoming"){
  const result=phase.score?'<span class="final-score">'+esc(game.home)+' <b>'+esc(phase.score)+'</b> '+esc(game.away)+'</span>':"";
  $("autoPanel").innerHTML='<div class="model-info phase-result">'+statusPill(phase.kind==="postponed"?"EXCLUIDA":"A_CONFIRMAR",phase.label)+
   (result||'<p>O resultado oficial ainda não foi sincronizado.</p>')+
   '<p>Este separador apresenta resultados ou estados do jogo. Não calculamos tips retroativas nem apostas em direto.</p></div>';
  return;
 }
 if(!model){
  $("autoPanel").innerHTML='<div class="no-stats"><strong>Sem tip fundamentada</strong><p>Há jogo no calendário, mas não há resultados históricos suficientes para este encontro. Não será apresentada uma seleção inventada.</p></div>'+renderContext(game);
  return;
 }
 const verdict=previewVerdict(game,model,prices),pick=verdict.tip;
 const stale=!state.analysis.generatedAt||Date.now()-Date.parse(state.analysis.generatedAt)>36*3600000;
 let html='<div class="model-info"><small>RESULTADOS REAIS · FOOTBALL-DATA</small><strong>Médias de golos para este encontro</strong>'+
   '<div class="model-xg"><div><b>'+esc(n(model.lambdaHome,2))+'</b><small>'+esc(game.home)+'</small></div><span>×</span><div><b>'+esc(n(model.lambdaAway,2))+'</b><small>'+esc(game.away)+'</small></div></div>'+
   '<p>Projeção matemática baseada no histórico (não é xG oficial). Amostra: '+esc(model.home?.sample||0)+' jogos da equipa da casa e '+esc(model.away?.sample||0)+' da equipa visitante.</p></div>';
 if(pick){
  html+='<div class="featured-pick"><div class="featured-pick-heading"><span>ESCOLHA DO MODELO</span>'+statusPill("OBSERVAR","◉ Observar")+'</div>'+
   '<strong>'+esc(pick.label)+'</strong><p>Uma opção estatística para analisares — <b>não é uma aposta validada</b>.</p>'+
   '<div class="featured-grid"><div><small>Prob. estimada</small><b>'+pct(pick.probability)+'</b></div><div><small>Odd mín. teórica</small><b>'+safeOdd(pick.minimumOdd)+'</b></div><div><small>Odd Betano</small><b>Por confirmar</b></div></div>'+
   '<button class="feature-action" data-manual-market="'+esc(pick.key)+'" type="button">Completar dados desta seleção ↗</button></div>';
 }else html+='<div class="no-stats"><strong>Sem seleção preferencial</strong><p>Os mercados modelados não cumprem os limites exploratórios mínimos para uma sugestão estatística.</p></div>';
 const groups=[["Resultado","RESULTADO FINAL"],["Golos","GOLOS / AMBAS MARCAM"],["Resultado exato","RESULTADO EXATO"]];
 for(const [group,title] of groups){
  const items=(model.markets||[]).filter(x=>x.group===group);
  if(!items.length)continue;
  html+='<details class="market-group"><summary>'+esc(title)+' <small>'+items.length+' mercados</small></summary>';
  html+=items.map(item=>{
   const q=prices[item.key],od=Number(q?.odd),hasOdd=Number.isFinite(od)&&od>1;
   const edge=hasOdd?item.probability-1/od-item.uncertainty:null;
   return '<div class="market-row"><div class="market-top"><strong>'+esc(item.label)+'</strong>'+statusPill("OBSERVAR","Observar")+'</div>'+
   '<div class="market-num"><div><small>Modelo</small><b>'+pct(item.probability)+'</b></div><div><small>Odd mín. do modelo</small><b class="green">'+safeOdd(item.minimumOdd)+'</b></div><div><small>Odd recebida</small><b>'+(hasOdd?safeOdd(od):"—")+'</b></div></div>'+
   '<div class="market-bottom"><span>'+(hasOdd?esc(q.bookmaker||"Fornecedor")+' · Edge preliminar: '+pct(edge):'Sem preço Betano confirmado')+'</span><button type="button" class="manual-open" data-manual-market="'+esc(item.key)+'">Validar ↗</button></div></div>';
  }).join("");
  html+='</details>';
 }
 html+='<div class="auto-warning"><strong>Porque não é uma Aposta?</strong> A projeção utiliza apenas o histórico Football-Data. As tuas regras exigem odds justas de mercado, consenso de pelo menos duas fontes independentes, verificações de contexto e odd confirmada na Betano.'+
 (stale?' Esta atualização estatística pode estar desatualizada.':'')+'</div>';
 html+=renderContext(game);
 html+='<div class="sources-foot">Poisson exploratório de resultados anteriores. Odd mínima ilustrativa calculada apenas com este modelo, <strong>não</strong> com a média ponderada de todas as tuas fontes. Não são apresentados cartões nem picks inventadas.</div>';
 $("autoPanel").innerHTML=html;
}
function openManual(key){
 const game=state.selected;if(!game)return;
 const item=modelFor(game)?.markets?.find(x=>x.key===key);
 const q=quoteFor(game,key);
 if(!item)return;
 $("manualDetails").open=true;
 $("selection").value=item.label;
 $("market").value=key.startsWith("CS_")?"correct":key.startsWith("1X2_")?"result":"goals";
 $("odds").value=q?.odd||"";
 $("priceSource").value="reference";
 $("p_fair").value=Number.isFinite(q?.fairProbability)?(q.fairProbability*100).toFixed(2):"";
 $("resultPanel").hidden=true;
 $("manualDetails").scrollIntoView({behavior:"smooth",block:"start"});
}

function store(){try{localStorage.setItem("edgy_betting_saved_v1",JSON.stringify(state.saved))}catch{}}
function isLive(game){return fixtureState(game).kind==="live";}
function statusText(g){return fixtureState(g).label;}
function logo(src,name){return safeImg(src)?'<img loading="lazy" referrerpolicy="no-referrer" alt="" src="'+esc(src)+'">':'<span class="placeholder-logo" aria-hidden="true"></span>';}
function uniqueGames(list){const ids=new Set();return list.filter(g=>{if(!g||!g.id||!g.home||!g.away||!g.utc||!Number.isFinite(Date.parse(g.utc)))return false;const key=g.home.toLowerCase()+"|"+g.away.toLowerCase()+"|"+localDate(g.utc);if(ids.has(key))return false;ids.add(key);return true;}).sort((a,b)=>a.utc.localeCompare(b.utc));}
function updateCounters(){
 const upcoming=state.games.filter(g=>isBettablePeriod(g));
 $("gameCount").textContent=String(upcoming.length);
 $("analysisCount").textContent=String(upcoming.filter(g=>Boolean(modelFor(g))).length);
 $("confirmedCount").textContent=String(upcoming.filter(g=>Object.keys(state.odds.matches?.[g.id]||{}).length>0).length);
 $("sidebarCount").textContent=String(state.games.length);$("savedCount").textContent=String(state.saved.length);
 $("gamesUpdated").textContent=state.generated?"Atualizado: "+localTime(state.generated):"Sem atualização confirmada";
 $("syncStatus").textContent=state.generated?"Dados: "+localTime(state.generated):"Sem sincronização";
 $("sourceLabel").textContent=state.source||"fonte não disponível";renderRadarOverview();
}
async function fallback(){
 // Fallback limitado: a chave pública gratuita devolve apenas alguns jogos por liga.
 const ids=[4328,4329,4331,4332,4334,4335];
 const jobs=ids.map(async id=>{try{
 const res=await fetch("https://www.thesportsdb.com/api/v1/json/123/eventsnextleague.php?id="+id,{signal:AbortSignal.timeout(7000)});
 if(!res.ok)return [];
 const data=await res.json();
 return (data.events||[]).map(e=>({id:"tsdb-"+e.idEvent,home:e.strHomeTeam,away:e.strAwayTeam,league:e.strLeague,leagueCode:e.idLeague,utc:e.strTimestamp?e.strTimestamp.replace(/Z?$/,"Z"):e.dateEvent+"T"+(e.strTime||"12:00:00")+"Z",status:e.strStatus||"NS",homeLogo:e.strHomeTeamBadge,awayLogo:e.strAwayTeamBadge,source:"TheSportsDB",division:2*0+1}));
 }catch{return [];}});return (await Promise.all(jobs)).flat();
}
async function loadGames(){
 $("syncStatus").textContent="A sincronizar…";$("reload").disabled=true;
 try{
  const response=await fetch("./data/fixtures.json?nocache="+Date.now(),{cache:"no-store"});
  if(!response.ok)throw new Error("O ficheiro de dados ainda não foi gerado.");
  const payload=await response.json();
  state.games=uniqueGames(payload.games||[]);
  state.source=payload.sources?.join(" + ")||"TheSportsDB";
  state.generated=payload.generatedAt||null;state.error=payload.message||"";
  const age=state.generated?Date.now()-Date.parse(state.generated):Infinity;
  if((!state.games.length||age>48*3600000)){
    const extra=await fallback();if(extra.length){state.games=uniqueGames([...state.games,...extra]);state.source+=" + TheSportsDB (fallback limitado)";}
  }
 }catch(error){
  state.error=error.message;state.generated=null;state.games=uniqueGames(await fallback());state.source=state.games.length?"TheSportsDB (fallback limitado)":"";
 }
 await loadIntelligence();
 if(!state.selected){
  const future=state.games.filter(g=>isBettablePeriod(g)).sort((a,b)=>a.utc.localeCompare(b.utc));
  state.selected=future.find(g=>modelFor(g))||future[0]||null;
  if(state.selected){$("analysisFields").disabled=false;$("analyze").disabled=false;}
 }
 $("reload").disabled=false;updateCounters();renderLeagues();renderGames();refreshSelection();renderAutoPanel();
}
function renderLeagues(){
 const available=Array.from(new Map(state.games.map(g=>[g.leagueCode||g.league,{key:g.leagueCode||g.league,label:g.league}])).values()).sort((a,b)=>a.label.localeCompare(b.label,"pt"));
 if(state.league!=="all"&&!available.some(g=>g.key===state.league))state.league="all";
 const total=state.games.length;
 $("leagues").innerHTML='<button type="button" class="league '+(state.league==="all"?"active":"")+'" data-league="all"><span>Todas as competições</span><small>'+total+'</small></button>'+
 available.map(item=>'<button type="button" class="league '+(state.league===item.key?"active":"")+'" data-league="'+esc(item.key)+'"><span>'+esc(item.label)+'</span><small>'+state.games.filter(g=>(g.leagueCode||g.league)===item.key).length+'</small></button>').join("");
}
function filteredGames(){
 const now=Date.now(),today=localDate(now),tomorrow=localDate(now+86400000);
 const games=state.games.filter(g=>{
  const phase=fixtureState(g,now),date=localDate(g.utc);
  if(state.query&&!(g.home+" "+g.away+" "+g.league).toLowerCase().includes(state.query))return false;
  if(state.league!=="all"&&(g.leagueCode||g.league)!==state.league)return false;
  if(state.filter==="upcoming"&&phase.kind!=="upcoming")return false;
  if(state.filter==="today"&&date!==today)return false;
  if(state.filter==="tomorrow"&&date!==tomorrow)return false;
  if(state.filter==="live"&&phase.kind!=="live")return false;
  if(state.filter==="results"&&!["finished","awaiting","postponed"].includes(phase.kind))return false;
  if(state.radar==="modeled"&&!modelFor(g))return false;
  if(state.radar==="priced"&&!Object.keys(state.odds.matches?.[g.id]||{}).length)return false;
  if(state.radar==="unmodeled"&&modelFor(g))return false;
  return true;
 });
 return games.sort((a,b)=>state.filter==="results"?b.utc.localeCompare(a.utc):a.utc.localeCompare(b.utc));
}
function renderGames(){
 const list=filteredGames();
 $("filterResult").textContent=list.length+" jogos";
 $("dateRangeLabel").textContent=state.generated?"Horário de Lisboa":"Fonte por sincronizar";
 if(!list.length){
  const message=state.filter==="live"?"Não há jogos em direto confirmados pela fonte.":state.filter==="results"?
   "Ainda não há resultados sincronizados para os dias disponíveis.":"Altera os filtros para veres outros encontros.";
  $("games").innerHTML='<div class="empty"><strong>Nenhum encontro encontrado</strong>'+message+(state.error?'<br><small>'+esc(state.error)+'</small>':"")+'</div>';
  return;
 }
 let date="",html="";
 for(const game of list.slice(0,120)){
  const today=localDate(game.utc),phase=fixtureState(game);
  if(today!==date){
   html+='<div class="day-heading">'+esc(niceDate(game.utc))+'</div>';
   date=today;
  }
  const value=phase.score||phase.label;
  const verdict=previewVerdict(game,modelFor(game),state.odds.matches?.[game.id]||{});
  const recommendation=verdict.tip?statusPill("OBSERVAR","◉ Observar"):
   (phase.kind==="finished"?statusPill("TERMINADO","Resultado"):
   (phase.kind==="postponed"?statusPill("EXCLUIDA","Adiado"):
    statusPill("SEM_DADOS",phase.kind==="upcoming"?"Sem tip":"A confirmar")));
  html+='<button type="button" class="game-card '+(state.selected?.id===game.id?"active":"")+
   '" data-game="'+esc(game.id)+'" aria-label="'+esc(game.home+" contra "+game.away+", "+phase.label)+'">'+
   '<span class="game-meta">'+(phase.kind==="live"?'<span class="live-badge">● DIRETO</span>':'<strong>'+esc(localTime(game.utc))+'</strong>')+
   '<small>'+esc(value)+'</small></span>'+
   '<span class="fixture"><span class="fixture-league">'+esc(game.league||"Futebol")+'</span>'+
   '<span class="teams"><span class="team">'+logo(game.homeLogo,game.home)+'<span class="team-name">'+esc(game.home)+'</span></span>'+
   '<span class="team">'+logo(game.awayLogo,game.away)+'<span class="team-name">'+esc(game.away)+'</span></span></span></span>'+
   '<span class="game-action"><span class="game-status">'+recommendation+'</span><small>'+(phase.kind==="finished"?"VER RESULTADO":"VER ANÁLISE")+' ↗</small></span>'+
   renderGamePreview(game)+'</button>';
 }
 if(list.length>120)html+='<div class="source-note">A mostrar 120 de '+list.length+' encontros. Filtra por liga, data ou pesquisa.</div>';
 $("games").innerHTML=html;
}
function refreshSelection(){
 if(!state.selected){$("selectedMatch").innerHTML='<div class="pick-placeholder"><span>◎</span><strong>Seleciona um jogo</strong><small>Escolhe um jogo da lista para iniciar a análise.</small></div>';return;}
 const g=state.games.find(x=>x.id===state.selected.id);if(g)state.selected=g;
 $("selectedMatch").innerHTML='<div class="pick-main"><small>'+esc(state.selected.league||"Jogo selecionado")+'</small><strong>'+esc(state.selected.home)+' × '+esc(state.selected.away)+'</strong><span>'+esc(niceDate(state.selected.utc))+' · '+esc(localTime(state.selected.utc))+' (Lisboa)</span></div>';
}
function selectGame(id){
 const game=state.games.find(x=>x.id===id);if(!game)return;
 state.selected=game;state.current=null;$("analysisForm").reset();$("analysisFields").disabled=!isBettablePeriod(game);$("analyze").disabled=!isBettablePeriod(game);$("resultPanel").hidden=true;updatePushField();refreshSelection();renderAutoPanel();renderGames();
 $("manualDetails").open=false;
 if(matchMedia("(max-width:700px)").matches){$("inspector").classList.add("is-open");document.body.classList.add("details-open");$("inspector").scrollTop=0;}
 else if(matchMedia("(max-width:1020px)").matches)$("inspector").scrollIntoView({behavior:"smooth",block:"start"});
}
function formInput(){
 const selected=state.selected,g=$("market").value,ctx=Number($("contextAdjustment").value)||0;
 const probs={};for(const key of ["fair","statarea","sporty","soccer","stataGoals","espn"])probs[key]=$("p_"+key).value;
 const adjustments={};for(const key of ["statarea","sporty","soccer","stataGoals","espn"])adjustments[key]=ctx;
 const bookmakers=Array.from(document.querySelectorAll(".movement-grid")).map(div=>({name:div.dataset.book,open:div.querySelector(".open").value,current:div.querySelector(".now").value}));
 return {matchId:selected?.id||"",kickoff:selected?.utc||null,day:selected?localDate(selected.utc):"",market:g,selection:$("selection").value.trim(),odds:$("odds").value,priceSource:$("priceSource").value,probabilities:probs,adjustments,bookmakers,pushProbability:$("pushProbability").value,crossLeague:$("crossLeague").checked,secondDivision:selected?.division===2,confirmedLineups:$("confirmedLineups").checked,criticalRotation:$("criticalRotation").checked,criticalWeather:$("criticalWeather").checked,bank:$("bankroll").value,weeklyLoss:$("weeklyLoss").value,maxPerDay:$("maxPerDay").value,minOdds:$("minOdds").value,maxOdds:$("maxOdds").value,prudence:$("prudence").value};
}
function showResult(input,result){
 const statusMap={APOSTA:"✓ Aposta",VERIFICAR:"⌕ Verificar",OBSERVAR:"◉ Observar",EXCLUIDA:"⛔ Excluída"};
 const pct=x=>n(x*100,1)+"%";const available=result.sources.length>0;
 const metrics=[["Prob. nossa",available?pct(result.p):"—"],["Prob. casa",Number(input.odds)>1?pct(result.implied):"—"],["Edge",available&&Number(input.odds)>1?pct(result.edge):"—"],["Edge ajustado",available&&Number(input.odds)>1?pct(result.adjusted):"—"],["Incerteza",available?pct(result.uncertainty):"—"],["Retorno esperado",available&&Number(input.odds)>1?pct(result.ev):"—"],["Odd mínima Betano",Number.isFinite(result.requiredOdds)?n(Math.ceil(result.requiredOdds*100)/100,2):"N/D"],["Stake máxima teórica",n(result.stake,2)+" €"]];
 const count=result.sources.length;
 $("resultPanel").dataset.status=result.status;
 $("resultPanel").innerHTML='<div class="result-head"><strong>Resultado da análise</strong><span class="status-tag '+result.status.toLowerCase()+'">'+statusMap[result.status]+'</span></div>'+
 '<div class="calc-grid">'+metrics.map(([label,value],i)=>'<div class="calc-box '+(i===3?"highlight":"")+'"><small>'+label+'</small><strong>'+esc(value)+'</strong></div>').join("")+'</div>'+
 '<p class="form-help">Fontes válidas: '+count+' · Consenso independente: '+result.consensus+' · Stake = menor de 1% da banca ou 10% de Kelly prudente. Não é uma aposta executada.</p>'+
 '<ul class="reasons">'+result.reasons.map(x=>'<li>'+esc(x)+'</li>').join("")+'</ul>'+
 '<div class="warnings">'+result.warnings.map(x=>'<div>• '+esc(x)+'</div>').join("")+'</div>'+
 '<button type="button" id="saveAnalysis" class="save-button" '+(!input.selection||!available||result.status==="EXCLUIDA"?"disabled":"")+'>＋ Guardar na lista de observação</button>';
 $("resultPanel").hidden=false;
 $("saveAnalysis")?.addEventListener("click",()=>saveResult(input,result));
}
function saveResult(input,result){
 if(!state.selected||!input.selection||!result.sources.length||result.status==="EXCLUIDA")return;
 const same=state.saved.filter(x=>x.matchId===input.matchId);
 if(same.length>=2||same.some(x=>(x.deps||[x.group]).some(dep=>(result.market.deps||[result.market.group]).includes(dep)))){alert("Máximo duas análises por jogo e não podem partilhar o mesmo grupo de mercado.");return;}
 const obj={id:Date.now().toString(36)+"-"+Math.random().toString(36).slice(2,7),matchId:input.matchId,day:input.day,home:state.selected.home,away:state.selected.away,market:input.market,group:result.market.group,deps:result.market.deps,selection:input.selection,odds:Number(input.odds),priceSource:input.priceSource,status:result.status,edgeAdjusted:result.adjusted,stake:result.stake,createdAt:new Date().toISOString()};
 state.saved.push(obj);store();updateCounters();$("saveAnalysis").textContent="✓ Guardado";$("saveAnalysis").disabled=true;
}
function renderSaved(){
 if(!state.saved.length){$("savedList").innerHTML='<div class="empty"><strong>Lista vazia</strong>Escolhe um jogo e guarda uma análise para a acompanhares aqui.</div>';return;}
 $("savedList").innerHTML=state.saved.slice().reverse().map(x=>'<article class="saved-item"><div class="saved-item-header"><span>'+esc(x.home)+' × '+esc(x.away)+'</span><button class="remove-button" data-remove="'+esc(x.id)+'" type="button">Remover</button></div><p>'+esc(MARKETS[x.market]?.label||x.market)+' · '+esc(x.selection)+'</p><small>'+esc(x.status)+' · Odd '+esc(n(x.odds,2))+' · Edge ajustado '+esc(n(x.edgeAdjusted*100,1))+'% · '+esc(x.priceSource==="betano"?"Betano confirmada na análise":"Odd por verificar")+'</small></article>').join("");
}
function closeInspector(){$("inspector").classList.remove("is-open");document.body.classList.remove("details-open");}
function setView(next){closeInspector();state.view=next;document.querySelector(".app-shell").dataset.view=next;$("matchesView").hidden=next!=="matches";$("savedView").hidden=next!=="saved";$("rulesView").hidden=next!=="rules";document.querySelectorAll("[data-view]").forEach(el=>el.classList.toggle("active",el.dataset.view===next));if(next==="saved")renderSaved();if(next==="matches")renderGames();}
function updatePushField(){$("pushField").hidden=!["void","quarter"].includes($("market").value);}
document.addEventListener("click",event=>{
 const close=event.target.closest("#closeInspector");if(close){closeInspector();return;}
 const game=event.target.closest("[data-game]");if(game){selectGame(game.dataset.game);return;}
 const lg=event.target.closest("[data-league]");if(lg){state.league=lg.dataset.league;renderLeagues();renderGames();return;}
 const range=event.target.closest("[data-range]");if(range){state.filter=range.dataset.range;document.querySelectorAll("[data-range]").forEach(b=>b.classList.toggle("selected",b.dataset.range===state.filter));renderGames();return;}
 const radar=event.target.closest("[data-radar]");if(radar){state.radar=radar.dataset.radar;document.querySelectorAll("[data-radar]").forEach(b=>b.classList.toggle("active",b.dataset.radar===state.radar));renderGames();return;}
 const openDetails=event.target.closest("[data-open-manual]");if(openDetails){$("manualDetails").open=true;$("manualDetails").scrollIntoView({behavior:"smooth",block:"start"});return;}
 const marketButton=event.target.closest("[data-manual-market]");if(marketButton){openManual(marketButton.dataset.manualMarket);return;}
 const view=event.target.closest("[data-view]");if(view){setView(view.dataset.view);return;}
 const remove=event.target.closest("[data-remove]");if(remove){state.saved=state.saved.filter(x=>x.id!==remove.dataset.remove);store();updateCounters();renderSaved();}
});
$("leagueSearch").addEventListener("input",e=>{state.query=e.target.value.toLowerCase().trim();renderGames()});
$("analysisForm").addEventListener("submit",e=>{e.preventDefault();if(!state.selected)return;const input=formInput(),result=evaluate(input,state.saved);state.current=result;showResult(input,result)});
$("fairCalc").addEventListener("click",()=>{
 const raw=[$("fairA").value,$("fairB").value,$("fairC").value];
 const odds=raw.filter(x=>x!=="").map(Number);
 const picked=Number($("fairOutcome").value);
 if(raw[0]==="" || raw[1]==="" || odds.length<2 || odds.length>3 || odds.some(x=>!Number.isFinite(x)||x<=1) || (raw[2]===""&&picked===2)){
  $("fairMessage").textContent="Indica duas ou três odds válidas e escolhe o resultado correspondente.";
  return;
 }
 const probabilities=odds.map(x=>1/x);
 const sum=probabilities.reduce((a,b)=>a+b,0);
 if(sum<=0 || sum<.85 || sum>1.5){$("fairMessage").textContent="Margem invulgar: verifica se as odds são do mesmo mercado e casa.";return;}
 const percent=probabilities[picked]/sum*100;
 $("p_fair").value=percent.toFixed(2);
 $("fairMessage").textContent="Probabilidade justa da seleção: "+n(percent,2)+"%. Margem total removida: "+n((sum-1)*100,2)+" p.p.";
 $("resultPanel").hidden=true;
});
$("market").addEventListener("change",updatePushField);
$("analysisForm").addEventListener("input",()=>{$("resultPanel").hidden=true;state.current=null;});
$("reload").addEventListener("click",loadGames);
$("clearSaved").addEventListener("click",()=>{if(!state.saved.length)return;if(confirm("Eliminar todas as análises guardadas neste dispositivo?")){state.saved=[];store();updateCounters();renderSaved()}});
window.addEventListener("keydown",event=>{if(event.key==="Escape")closeInspector();});
loadGames();
