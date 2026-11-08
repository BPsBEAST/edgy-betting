// EDGY Betting — deterministic, source-aware evaluation. No external network calls.
export const MARKETS = {
  result: {label:"Resultado / dupla hipótese", group:"resultado",deps:["resultado"],difficulty:0.022},
  goals: {label:"Golos / ambas marcam",group:"golos",deps:["golos"],difficulty:0.027},
  half: {label:"Intervalo",group:"resultado",deps:["resultado"],difficulty:0.037},
  minutes: {label:"Minutos / eventos",group:"golos",deps:["golos"],difficulty:0.064},
  combo: {label:"Combinada do jogo",group:"combinada",deps:["resultado","golos","combinada"],difficulty:0.065},
  correct: {label:"Resultado exato",group:"resultado",deps:["resultado","golos"],difficulty:0.09},
  corners: {label:"Cantos",group:"cantos",deps:["cantos"],difficulty:0.065},
  shots: {label:"Remates",group:"remates",deps:["remates"],difficulty:0.069},
  void: {label:"Empate anula / asiático inteiro",group:"resultado",deps:["resultado"],difficulty:0.038},
  quarter: {label:"Handicap asiático de quarto",group:"resultado",deps:["resultado"],difficulty:0.09}
};
const SOURCES=[
 {key:"fair",name:"Mercado justo (sem margem)",provider:"Mercado",weight:3},
 {key:"statarea",name:"Statarea — previsão",provider:"Statarea",weight:1},
 {key:"sporty",name:"SportyTrader — previsão",provider:"SportyTrader",weight:1},
 {key:"soccer",name:"SoccerVital — golos / casa-fora",provider:"SoccerVital",weight:.5},
 {key:"stataGoals",name:"Statarea — médias de golos",provider:"Statarea",weight:.5},
 {key:"espn",name:"ESPN — cantos / remates",provider:"ESPN",weight:1}
];
export function validProbability(p){return p!==""&&p!==null&&p!==undefined&&Number.isFinite(Number(p))&&Number(p)>=0&&Number(p)<=100;}
export function clamp(x,min,max){return Math.min(max,Math.max(min,x));}
export function evaluate(input={}, existing=[]){
 const reasons=[],warnings=[];
 const market=MARKETS[input.market]||MARKETS.result;
 const odds=Number(input.odds),bank=Number(input.bank||0);
 const prudent=clamp(Number(input.prudence)||1,0,4);
 const minOdds=Number(input.minOdds)||1.3,maxOdds=Number(input.maxOdds)||5;
 const probabilities=input.probabilities||{};
 const cross=Boolean(input.crossLeague);
 const sources=SOURCES.flatMap(s=>{
   const p=probabilities[s.key];
   if(!validProbability(p))return [];
   if(s.key==="espn"&&!["corners","shots"].includes(input.market))return [];
   if(["corners","shots"].includes(input.market)&&s.key==="soccer")return [];
   if(["soccer","stataGoals"].includes(s.key)&&["correct","corners","shots","void","quarter","half","minutes","combo"].includes(input.market))return [];
   const adjustment=s.key==="fair"?0:clamp(Number(input.adjustments?.[s.key])||0,-20,20);
   return [{...s,p:clamp((Number(p)+adjustment)/100,0,1),weight:cross&&["soccer","stataGoals"].includes(s.key)?.15:s.weight,adjustment}];
 });
 const totalWeight=sources.reduce((a,s)=>a+s.weight,0);
 const p=totalWeight?sources.reduce((a,s)=>a+s.p*s.weight,0)/totalWeight:0;
 const dispersion=totalWeight?Math.sqrt(sources.reduce((a,s)=>a+s.weight*(s.p-p)**2,0)/totalWeight):0;
 let uncertainty=(market.difficulty+dispersion*.85+(sources.length<3?.025:0))*(input.secondDivision?1.10:1);
 const implied=odds>1?1/odds:0;
 let push=0,winProb=p,equivalent=p,ev=0;
 if(["void","quarter"].includes(input.market)){
  push=validProbability(input.pushProbability)?Number(input.pushProbability)/100:0;
  if(push>=1){warnings.push("Devolução inválida.");push=0;}
  if(winProb>1-push){warnings.push("Probabilidade de vitória superior à parcela sem devolução.");}
  equivalent=push<1?clamp(winProb/(1-push),0,1):0;
 }
 const edge=(["void","quarter"].includes(input.market)?equivalent:p)-implied;
 const adjusted=edge-prudent*uncertainty;
 ev=odds>1?winProb*(odds-1)-Math.max(0,1-winProb-push):0;
 const cautious=clamp((["void","quarter"].includes(input.market)?equivalent:p)-uncertainty,0,1);
 const kelly=odds>1?Math.max(0,(cautious*odds-1)/(odds-1)):0;
 const stake=clamp(Math.min(bank*.01,bank*.1*kelly),0,bank);
 const minimumOdd=(["void","quarter"].includes(input.market)?equivalent:p)-prudent*uncertainty-.03;
 const requiredOdds=minimumOdd>0?1/minimumOdd:Infinity;
 const unique=[...new Set(sources.filter(s=>(["void","quarter"].includes(input.market)&&push<1?s.p/(1-push):s.p)>implied).map(s=>s.provider))];
 const records=Array.isArray(input.bookmakers)?input.bookmakers:[];
 const moves=records.filter(x=>validProbability(x.open)&&validProbability(x.current)).map(x=>({name:x.name,delta:(Number(x.current)-Number(x.open))/100}));
 const negativeMoves=moves.filter(x=>x.delta<-.015).length;
 const exitTrend=moves.length>=2&&negativeMoves>moves.length/2;
 const sameGame=existing.filter(x=>x.matchId===input.matchId);
 const correlated=sameGame.some(x=>(x.deps||[x.group]).some(dep=>(market.deps||[market.group]).includes(dep)));
 const maxPerMatch=sameGame.length>=2;
 const dayCount=existing.filter(x=>x.day===input.day).length;
 const maxPerDay=Math.max(0,Math.floor(Number(input.maxPerDay)||0));
 const weeklyLoss=Number(input.weeklyLoss)||0;
 let status="OBSERVAR";
 if(input.criticalRotation||input.criticalWeather){status="EXCLUIDA";reasons.push("Fator crítico registado: rotação ou meteorologia incompatível.");}
 else if(input.market==="quarter"){reasons.push("Linhas asiáticas de quarto exigem modelação separada de meia vitória/derrota.");}
 else if(input.market==="void" && (winProb>1-push || !validProbability(input.pushProbability))){reasons.push("No mercado com devolução, introduz a probabilidade de devolução e probabilidades de vitória coerentes.");}
 else if(input.kickoff && Number.isFinite(Date.parse(input.kickoff)) && Date.parse(input.kickoff)<=Date.now()){reasons.push("Jogo já iniciado ou terminado: sem modelo in-play validado, não aprovar apostas.");}
 else if(!Number.isFinite(odds)||odds<=1){reasons.push("Introduz uma odd decimal real e válida.");}
 else if(!sources.length){reasons.push("Faltam probabilidades das fontes. Não existem estimativas automáticas inventadas.");}
 else if(["corners","shots"].includes(input.market)){reasons.push("Sem duas fontes estatísticas independentes para cantos ou remates, manter em observação.");}
 else if(sources.length<2 || unique.length<2){reasons.push("É necessário consenso de pelo menos duas fontes independentes que vejam valor.");}
 else if(odds<minOdds||odds>maxOdds){reasons.push("Odd fora dos limites configurados.");}
 else if(adjusted<.03){reasons.push("Edge ajustado inferior a 3%.");}
 else if(Math.abs(p-implied)>.18){reasons.push("Estimativa demasiado afastada do mercado (>18 p.p.): possível informação não refletida nas fontes.");}
 else if(exitTrend){reasons.push("Probabilidade justa a cair na maioria das casas comparadas: sinal contrário.");}
 else if(correlated||maxPerMatch){reasons.push("Limite de duas escolhas por jogo ou correlação com uma escolha já guardada.");}
 else if(maxPerDay>0&&dayCount>=maxPerDay){reasons.push("Limite diário de seleções já atingido.");}
 else if(weeklyLoss<=-3){reasons.push("Stop semanal: perda de 3% ou mais da banca.");}
 else if(!input.confirmedLineups){reasons.push("Onzes, ausências e contexto sem verificação: manter em observação.");}
 else if(input.priceSource!=="betano"){status="VERIFICAR";reasons.push("Odd de referência ou por confirmar. Verificar no boletim da Betano.");}
 else {status="APOSTA";reasons.push("Critérios quantitativos cumpridos com os dados introduzidos. Confirmar antes de qualquer decisão.");}
 if(sources.length===1)warnings.push("Fonte única: elevada incerteza.");
 if(!moves.length)warnings.push("Sem registos de movimento justo de mercado; fluxo financeiro não mensurável.");
 if(moves.length===1)warnings.push("Uma única casa não permite confirmar tendência de mercado.");
 if(["corners","shots"].includes(input.market)&&sources.length===1)warnings.push("A ESPN é apenas uma fonte: sem segunda fonte independente, observar.");
 if(uncertainty>.10)warnings.push("Incerteza muito elevada ou fontes divergentes.");
 if(!input.confirmedLineups)warnings.push("Onzes, lesões, descanso e contexto não confirmados automaticamente.");
 return {status,reasons,warnings,market,sources,p,implied,edge,adjusted,uncertainty,ev,stake,kelly,cautious,push,equivalent,requiredOdds,consensus:unique.length,bookmakerMoves:moves,exitTrend,correlated,maxPerMatch};
}
