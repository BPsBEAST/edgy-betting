import {MARKETS,evaluate} from "./src/engine.js";
const $=id=>document.getElementById(id);
const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const safeImg=url=>typeof url==="string"&&/^https:\/\/[a-z0-9.-]+\//i.test(url)?url:"";
const localDate=d=>new Intl.DateTimeFormat("sv-SE",{timeZone:"Europe/Lisbon",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date(d));
const localTime=d=>new Intl.DateTimeFormat("pt-PT",{timeZone:"Europe/Lisbon",hour:"2-digit",minute:"2-digit"}).format(new Date(d));
const niceDate=d=>new Intl.DateTimeFormat("pt-PT",{timeZone:"Europe/Lisbon",weekday:"long",day:"numeric",month:"long"}).format(new Date(d));
const n=(v,d=1)=>Number.isFinite(v)?new Intl.NumberFormat("pt-PT",{minimumFractionDigits:d,maximumFractionDigits:d}).format(v):"—";
const readSaved=()=>{try{let list=JSON.parse(localStorage.getItem("edgy_betting_saved_v1")||"[]");return Array.isArray(list)?list.filter(x=>x&&x.matchId):[]}catch{return []}};
const state={games:[],source:"",generated:null,error:"",selected:null,filter:"all",league:"all",query:"",view:"matches",saved:readSaved(),current:null,radar:"all",analysis:{models:{},generatedAt:null},odds:{matches:{},generatedAt:null}};

async function loadIntelligence(){
 const get=async name=>{
  try{
   const response=await fetch("./data/"+name+"?v="+Date.now(),{cache:"no-store"});
   if(!response.ok)throw new Error("Feed "+name+" indisponível");
   return await response.json();
  }catch{return null;}
 };
 const [analysis,odds]=await Promise.all([get("analysis.json"),get("market_odds.json")]);
 state.analysis=analysis&&analysis.models&&typeof analysis.models==="object"?analysis:{models:{},generatedAt:null};
 state.odds=odds&&odds.matches&&typeof odds.matches==="object"?odds:{matches:{},generatedAt:null};
}
function modelFor(game){return state.analysis.models?.[game?.id]||null;}
function quoteFor(game,key){return state.odds.matches?.[game?.id]?.[key]||null;}
function percentage(v){return typeof v==="number"&&Number.isFinite(v)?n(v*100,1)+"%":"—";}
function renderRadarOverview(){
 const count=state.games.filter(g=>!!modelFor(g)).length;
 const priced=state.games.filter(g=>!!Object.keys(state.odds.matches?.[g.id]||{}).length).length;
 const timestamp=state.analysis.generatedAt?localTime(state.analysis.generatedAt):"não disponível";
 $("radarOverview").innerHTML='<span>◎</span><b>'+count+' jogos com projeções estatísticas</b> · '+priced+' com odds de referência. <strong>0 apostas automáticas aprovadas</strong><br>'+
 '<small>Modelo Football-Data/Poisson exploratório; atualização: '+esc(timestamp)+'. Só uma fonte estatística, não equivale ao consenso obrigatório. Os jogos sem modelo continuam visíveis.</small>';
}
function renderGamePreview(game){
 const model=modelFor(game),quotes=state.odds.matches?.[game.id]||{};
 const hasPrice=Object.keys(quotes).length>0;
 if(!model)return '<span class="game-preview no-data"><span>◉ Sem histórico suficiente para análise automática</span>'+(hasPrice?'<span class="price-flag">ODDS DE REFERÊNCIA</span>':"")+'</span>';
 const winner=(model.markets||[]).filter(x=>x.key?.startsWith("1X2_"));
 const total=model.markets?.find(x=>x.key==="O25");
 const forecast=winner.length===3?
  '<span class="forecast-mini"><span>1 <b>'+percentage(winner[0].probability)+'</b></span><span>X <b>'+percentage(winner[1].probability)+'</b></span><span>2 <b>'+percentage(winner[2].probability)+'</b></span></span>':"";
 return '<span class="game-preview"><span class="forecast-mini">'+forecast+(total?'<span>+2,5 <b>'+percentage(total.probability)+'</b></span>':"")+'</span><span class="forecast-note">'+(hasPrice?'<span class="price-flag">◎ ODDS DE REFERÊNCIA</span>':'◉ OBSERVAR · SEM ODD CONFIRMADA')+'</span></span>';
}
function renderAutoPanel(){
 const game=state.selected;
 if(!game){$("autoPanel").innerHTML='<div class="auto-empty">Seleciona um jogo para veres os mercados e estatísticas calculadas.</div>';return;}
 const model=modelFor(game),prices=state.odds.matches?.[game.id]||{};
 const age=state.analysis.generatedAt?Date.now()-Date.parse(state.analysis.generatedAt):Infinity;
 const stale=!Number.isFinite(age)||age>36*3600000;
 const kickoff=Date.parse(game.utc);
 const inProgress=Number.isFinite(kickoff)&&kickoff<=Date.now();
 let html="";
 if(!model){
   html='<div class="no-stats"><strong>◉ Sem modelo estatístico validável</strong><p>O calendário deste jogo está disponível, mas ainda não existem resultados históricos suficientes, ou não há integração ESPN compatível, para estimar probabilidades sem inventar dados.</p></div>';
   const options=Object.entries(prices).slice(0,9);
   if(options.length){
    html+='<div class="auto-section-label">ODDS DE REFERÊNCIA DISPONÍVEIS</div>'+
      options.map(([key,item])=>'<div class="market-row"><div class="market-top"><strong>'+esc(key)+'</strong><span>Verificar</span></div><div class="market-bottom">'+esc(item.bookmaker||"Fornecedor")+' · odd '+esc(n(Number(item.odd),2))+' · sem avaliação estatística</div></div>').join("");
   }
 }else{
   html='<div class="model-info"><small>FOOTBALL-DATA · RESULTADOS REAIS</small><strong>Projeção de golos</strong>'+
    '<div class="model-xg"><div><b>'+esc(n(model.lambdaHome,2))+'</b><small>'+esc(game.home)+'</small></div><span>×</span><div><b>'+esc(n(model.lambdaAway,2))+'</b><small>'+esc(game.away)+'</small></div></div>'+
    '<p>Médias históricas estimadas por Poisson (não são xG oficiais). Casa: '+esc(model.home?.homeGames||0)+' partidas em casa. Fora: '+esc(model.away?.awayGames||0)+' partidas fora.</p></div>';
   const groups=[["Resultado","RESULTADO FINAL"],["Golos","GOLOS E AMBAS MARCAM"],["Resultado exato","RESULTADO EXATO"]];
   for(const [group,label] of groups){
    const items=(model.markets||[]).filter(item=>item.group===group);
    if(!items.length)continue;
    html+='<div class="auto-section-label">'+label+'</div>';
    html+=items.map(item=>{
      const q=prices[item.key],odd=Number(q?.odd),hasOdd=Number.isFinite(odd)&&odd>1;
      const edge=hasOdd?item.probability-1/odd:null;
      const adjusted=hasOdd?edge-item.uncertainty:null;
      const candidate=hasOdd&&adjusted>=.03;
      // Never approve without required named prediction sources and a confirmed Betano slip.
      const minOdd=Number.isFinite(item.minimumOdd)?n(item.minimumOdd,2):"N/D";
      return '<div class="market-row '+(candidate?"highlight-model":"")+'"><div class="market-top"><strong>'+esc(item.label)+'</strong><span>'+(candidate?'EDGE PRELIMINAR':'OBSERVAR')+'</span></div>'+
        '<div class="market-num"><div><small>Modelo histórico</small><b>'+percentage(item.probability)+'</b></div><div><small>Odd mínima teórica</small><b class="green">'+minOdd+'</b></div><div><small>Odd recolhida</small><b>'+(hasOdd?esc(n(odd,2)):"—")+'</b></div></div>'+
        '<div class="market-bottom"><span>'+(hasOdd?esc(q.bookmaker)+' · Edge ajust. exploratório: '+percentage(adjusted):'A aguardar odd da Betano')+'</span><button type="button" class="manual-open" data-manual-market="'+esc(item.key)+'">Detalhes ↗</button></div></div>';
    }).join("");
   }
   html+='<div class="auto-warning">Nenhum mercado pode passar a <b>APOSTA</b> apenas com este modelo. Faltam a comparação com Statarea/SportyTrader/SoccerVital, o consenso mínimo, ausências/onzes e confirmação da odd no boletim da Betano.'+
     (stale?' Os dados estatísticos podem estar desatualizados.':'')+(inProgress?' Este jogo já começou: o modelo pré-jogo não deve ser utilizado como previsão em direto.':'')+'</div>';
 }
 html+='<div class="sources-foot">Fonte de resultados: Football-Data.co.uk (CSV da época corrente). Odds: '+(state.odds.hasCredentials?'API-Football — referência não confirmada':'nenhum fornecedor com chave configurada')+'. Minutos, cantos, remates, cartões e asiáticos de quarto não são aprovados automaticamente sem dados específicos suficientes.</div>';
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
function isLive(game){return ["LIVE","IN_PLAY","HT","1H","2H","ET","PEN"].includes(game.status);}
function statusText(g){if(isLive(g))return "AO VIVO";if(["FT","FINISHED"].includes(g.status))return "TERMINADO";if(["POSTPONED","PST"].includes(g.status))return "ADIADO";return "AGENDADO";}
function logo(src,name){return safeImg(src)?'<img loading="lazy" referrerpolicy="no-referrer" alt="" src="'+esc(src)+'">':'<span class="placeholder-logo" aria-hidden="true"></span>';}
function uniqueGames(list){const ids=new Set();return list.filter(g=>{if(!g||!g.id||!g.home||!g.away||!g.utc||!Number.isFinite(Date.parse(g.utc)))return false;const key=g.home.toLowerCase()+"|"+g.away.toLowerCase()+"|"+localDate(g.utc);if(ids.has(key))return false;ids.add(key);return true;}).sort((a,b)=>a.utc.localeCompare(b.utc));}
function updateCounters(){
 $("gameCount").textContent=String(state.games.length);$("analysisCount").textContent=String(Object.keys(state.analysis.models||{}).length);$("confirmedCount").textContent=String(Object.keys(state.odds.matches||{}).length);
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
  const future=state.games.filter(g=>Date.parse(g.utc)>=Date.now()).sort((a,b)=>a.utc.localeCompare(b.utc));
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
 const now=new Date(),today=localDate(now),tomorrow=localDate(new Date(now.getTime()+86400000));
 return state.games.filter(g=>{
 const query=(g.home+" "+g.away+" "+g.league).toLowerCase();
 if(state.query&&!query.includes(state.query))return false;
 if(state.league!=="all"&&(g.leagueCode||g.league)!==state.league)return false;
 if(state.filter==="today"&&localDate(g.utc)!==today)return false;
 if(state.filter==="tomorrow"&&localDate(g.utc)!==tomorrow)return false;
 if(state.filter==="live"&&!isLive(g))return false;
 if(state.filter==="all"&&Date.parse(g.utc)<Date.now()-6*3600000)return false;
 if(state.radar==="modeled"&&!state.analysis.models?.[g.id])return false;
 if(state.radar==="priced"&&!Object.keys(state.odds.matches?.[g.id]||{}).length)return false;
 if(state.radar==="unmodeled"&&state.analysis.models?.[g.id])return false;
 return true;
 });
}
function renderGames(){
 const list=filteredGames();$("filterResult").textContent=list.length+" encontrados";
 $("dateRangeLabel").textContent=state.generated?"Fuso: Lisboa":"A aguardar dados";
 if(!list.length){$("games").innerHTML='<div class="empty"><strong>'+(!state.games.length?"Ainda não há calendário disponível":"Nenhum jogo encontrado")+'</strong>'+
 (state.games.length?"Altera os filtros para veres outros encontros.":"A sincronização automática depende do GitHub Actions e da cobertura dos fornecedores. Não são apresentados jogos fictícios.")+
 (state.error?'<br><small>'+esc(state.error)+'</small>':"")+'</div>';return;}
 let lastDate="";
 $("games").innerHTML=list.map(game=>{
 const date=localDate(game.utc),header=date===lastDate?"":'<div class="day-heading">'+esc(niceDate(game.utc))+'</div>';lastDate=date;
 const live=isLive(game);
 const score=game.homeScore!==null&&game.homeScore!==undefined&&game.awayScore!==null&&game.awayScore!==undefined?game.homeScore+" : "+game.awayScore:"";
 return header+'<button type="button" class="game-card '+(state.selected?.id===game.id?"active":"")+'" data-game="'+esc(game.id)+'">'+
 '<span class="game-meta">'+(live?'<span class="live-badge">● LIVE</span>':'<strong>'+esc(localTime(game.utc))+'</strong>')+'<small>'+esc(score||statusText(game))+'</small></span>'+
 '<span class="fixture"><span class="fixture-league">'+esc(game.league||"Futebol")+'</span><span class="teams"><span class="team">'+logo(game.homeLogo,game.home)+'<span class="team-name">'+esc(game.home)+'</span></span><span class="team">'+logo(game.awayLogo,game.away)+'<span class="team-name">'+esc(game.away)+'</span></span></span></span>'+
 '<span class="game-action"><b>VER DADOS</b><span>↗</span></span>'+renderGamePreview(game)+'</button>';
 }).join("");
}
function refreshSelection(){
 if(!state.selected){$("selectedMatch").innerHTML='<div class="pick-placeholder"><span>◎</span><strong>Seleciona um jogo</strong><small>Escolhe um jogo da lista para iniciar a análise.</small></div>';return;}
 const g=state.games.find(x=>x.id===state.selected.id);if(g)state.selected=g;
 $("selectedMatch").innerHTML='<div class="pick-main"><small>'+esc(state.selected.league||"Jogo selecionado")+'</small><strong>'+esc(state.selected.home)+' × '+esc(state.selected.away)+'</strong><span>'+esc(niceDate(state.selected.utc))+' · '+esc(localTime(state.selected.utc))+' (Lisboa)</span></div>';
}
function selectGame(id){
 const game=state.games.find(x=>x.id===id);if(!game)return;
 state.selected=game;state.current=null;$("analysisForm").reset();$("analysisFields").disabled=false;$("analyze").disabled=false;$("resultPanel").hidden=true;updatePushField();refreshSelection();renderAutoPanel();renderGames();
 $("manualDetails").open=false;
 if(matchMedia("(max-width:1020px)").matches)$("inspector").scrollIntoView({behavior:"smooth",block:"start"});
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
function setView(next){state.view=next;$("matchesView").hidden=next!=="matches";$("savedView").hidden=next!=="saved";document.querySelectorAll("[data-view]").forEach(el=>el.classList.toggle("active",el.dataset.view===next));if(next==="saved")renderSaved();}
function updatePushField(){$("pushField").hidden=!["void","quarter"].includes($("market").value);}
document.addEventListener("click",event=>{
 const game=event.target.closest("[data-game]");if(game){selectGame(game.dataset.game);return;}
 const lg=event.target.closest("[data-league]");if(lg){state.league=lg.dataset.league;renderLeagues();renderGames();return;}
 const range=event.target.closest("[data-range]");if(range){state.filter=range.dataset.range;document.querySelectorAll("[data-range]").forEach(b=>b.classList.toggle("selected",b.dataset.range===state.filter));renderGames();return;}
 const radar=event.target.closest("[data-radar]");if(radar){state.radar=radar.dataset.radar;document.querySelectorAll("[data-radar]").forEach(b=>b.classList.toggle("active",b.dataset.radar===state.radar));renderGames();return;}
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
loadGames();
