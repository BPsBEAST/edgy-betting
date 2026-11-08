// Pure fixture and preview rules. Never equate Poisson output to approved picks.
const FINISHED = new Set(["FT","AET","AFTER_EXTRA_TIME","STATUS_FULL_TIME","STATUS_FINAL","FINISHED","FULL_TIME","FINAL","STATUS_FULL_TIME_PENALTIES"]);
const LIVE = new Set(["LIVE","IN_PLAY","STATUS_IN_PROGRESS","STATUS_HALFTIME","HT","1H","2H","ET","PEN","STATUS_EXTRA_TIME","STATUS_PENALTY_SHOOTOUT"]);
const POSTPONED = new Set(["PST","POSTPONED","STATUS_POSTPONED","CANC","CANCELLED","STATUS_CANCELED","ABD","ABANDONED","SUSPENDED"]);
function numericScore(value) {return value!==null&&value!==undefined&&value!==""&&Number.isFinite(Number(value))?Number(value):null;}
export function fixtureState(game={},now=Date.now()){
 const code=String(game.status||"").toUpperCase();
 const t=Date.parse(game.utc||"");
 const home=numericScore(game.homeScore),away=numericScore(game.awayScore);
 const score=home!==null&&away!==null?home+"–"+away:null;
 if(POSTPONED.has(code))return {kind:"postponed",label:"Adiado",score:null};
 if(FINISHED.has(code))return {kind:"finished",label:"Terminado",score};
 if(LIVE.has(code))return {kind:"live",label:"Em direto",score};
 if(!Number.isFinite(t))return {kind:"unverified",label:"Data por confirmar",score};
 if(t<=now)return {kind:"awaiting",label:"Resultado por confirmar",score:null};
 return {kind:"upcoming",label:"Por começar",score:null};
}
export function isBettablePeriod(game,now=Date.now()){
 return fixtureState(game,now).kind==="upcoming";
}
export function selectPreview(model,quotes={}){
 if(!model||!Array.isArray(model.markets))return null;
 const eligible=model.markets.filter(x=>
  x&&Number.isFinite(x.probability)&&Number.isFinite(x.uncertainty)&&
  x.probability>=.50&&x.probability<=.88&&Number.isFinite(x.minimumOdd)&&
  x.minimumOdd>=1.25&&x.minimumOdd<=5&&
  !String(x.key||"").startsWith("CS_")
 );
 if(!eligible.length)return null;
 const priority={O25:0, U25:0, BTTS_Y:0, BTTS_N:0, "1X2_H":1, "1X2_A":1, "1X2_D":2, O15:3, U15:3};
 // Prefer substantive/evaluable markets rather than just the biggest raw p.
 eligible.sort((a,b)=>{
  const priceA=Number(quotes[a.key]?.odd),priceB=Number(quotes[b.key]?.odd);
  const aPriced=Number.isFinite(priceA)&&priceA>1;
  const bPriced=Number.isFinite(priceB)&&priceB>1;
  const aEdge=aPriced?a.probability-1/priceA-a.uncertainty:-1;
  const bEdge=bPriced?b.probability-1/priceB-b.uncertainty:-1;
  if(aPriced!==bPriced)return Number(bPriced)-Number(aPriced);
  if(aPriced&&bPriced&&Math.abs(aEdge-bEdge)>.015)return bEdge-aEdge;
  return (priority[a.key]??5)-(priority[b.key]??5) || (b.probability-b.uncertainty)-(a.probability-a.uncertainty);
 });
 return eligible[0];
}
export function previewVerdict(game,model,quotes={},now=Date.now()){
 const state=fixtureState(game,now);
 if(state.kind==="finished")return {status:"TERMINADO",reason:"Resultado final do jogo",tip:null};
 if(state.kind==="postponed")return {status:"EXCLUIDA",reason:"Jogo adiado ou cancelado",tip:null};
 if(state.kind==="live")return {status:"SEM_INPLAY",reason:"O modelo não avalia apostas em direto",tip:null};
 if(state.kind==="awaiting"||state.kind==="unverified")return {status:"A_CONFIRMAR",reason:"O jogo já começou ou falta atualizar o resultado",tip:null};
 if(!model)return {status:"SEM_DADOS",reason:"Faltam resultados históricos suficientes para estimar este mercado",tip:null};
 const tip=selectPreview(model,quotes);
 if(!tip)return {status:"OBSERVAR",reason:"Sem seleção estatística suficientemente sustentada",tip:null};
 const q=quotes[tip.key],odd=Number(q?.odd);
 const priced=Number.isFinite(odd)&&odd>1;
 const edge=priced?tip.probability-1/odd:null;
 const adjusted=edge===null?null:edge-tip.uncertainty;
 const requirements=[
  {key:"form",label:"Histórico",ready:true,detail:"Modelo de resultados anteriores"},
  {key:"sources",label:"Consenso 2 fontes",ready:false,detail:"Statarea/SportyTrader e médias por verificar"},
  {key:"odds",label:"Odd Betano",ready:false,detail:priced?"Odd externa é só referência":"Ainda sem odd recolhida"},
  {key:"context",label:"Contexto",ready:false,detail:"Onzes, ausências e meteorologia por verificar"},
  {key:"edge",label:"Edge ≥ 3 p.p.",ready:priced&&adjusted>=.03,detail:priced?"Edge do modelo: "+(adjusted*100).toFixed(1)+" p.p.":"Requer odd e fontes independentes"}
 ];
 // A single uncalibrated historical model is not one of the user's required
 // Statarea/SportyTrader/SoccerVital probabilities. No automated bet approval.
 return {status:"OBSERVAR",reason:"Sugestão estatística, não aposta validada: falta consenso e confirmação na Betano",tip,
  quote:priced?q:null,adjusted,requirements};
}
