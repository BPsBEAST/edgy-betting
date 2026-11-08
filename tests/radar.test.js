import test from "node:test";
import assert from "node:assert/strict";
import {fixtureState,isBettablePeriod,selectPreview,previewVerdict} from "../src/radar.js";
const NOW=Date.parse("2026-11-08T17:00:00Z");
const future={id:"fixture",status:"NS",utc:"2026-11-09T18:00:00Z",home:"Porto",away:"Braga"};
const past={...future,utc:"2026-11-07T18:00:00Z"};
const model={markets:[
 {key:"O25",label:"Mais de 2,5 golos",group:"Golos",probability:.64,uncertainty:.06,minimumOdd:1.82},
 {key:"1X2_H",label:"Vitória casa",group:"Resultado",probability:.58,uncertainty:.05,minimumOdd:2},
 {key:"CS_2_0",label:"Resultado exato 2-0",group:"Resultado exato",probability:.17,uncertainty:.12,minimumOdd:9}
]};
test("upcoming fixtures only include future games",()=>{
 assert.equal(fixtureState(future,NOW).kind,"upcoming");
 assert.equal(isBettablePeriod(future,NOW),true);
 assert.equal(isBettablePeriod(past,NOW),false);
});
test("full time status including ESPN is recognized and displays real score",()=>{
 const result=fixtureState({...past,status:"STATUS_FULL_TIME",homeScore:2,awayScore:1},NOW);
 assert.equal(result.kind,"finished");
 assert.equal(result.score,"2–1");
});
test("past fixture without a verified result never appears as upcoming",()=>{
 const result=fixtureState({...past,status:"NS",homeScore:null,awayScore:null},NOW);
 assert.equal(result.kind,"awaiting");
 assert.equal(result.score,null);
});
test("live fixture has score but no pre-match tip",()=>{
 const game={...past,status:"STATUS_IN_PROGRESS",homeScore:1,awayScore:0};
 assert.equal(fixtureState(game,NOW).kind,"live");
 assert.equal(previewVerdict(game,model,{},NOW).tip,null);
});
test("postponed match is excluded and not assigned a tip",()=>{
 const result=previewVerdict({...future,status:"STATUS_POSTPONED"},model,{},NOW);
 assert.equal(result.status,"EXCLUIDA");
 assert.equal(result.tip,null);
});
test("completed games show results instead of retroactively generated tips",()=>{
 const result=previewVerdict({...past,status:"FT",homeScore:1,awayScore:1},model,{},NOW);
 assert.equal(result.status,"TERMINADO");assert.equal(result.tip,null);
});
test("preview names a concrete selection without claiming an approved bet",()=>{
 const result=previewVerdict(future,model,{},NOW);
 assert.equal(result.status,"OBSERVAR");
 assert.equal(result.tip.label,"Mais de 2,5 golos");
 assert.ok(result.requirements.some(x=>x.key==="sources"&&!x.ready));
 assert.ok(result.requirements.some(x=>x.key==="odds"&&!x.ready));
});
test("no historical model means no invented tip",()=>{
 const result=previewVerdict(future,null,{},NOW);
 assert.equal(result.status,"SEM_DADOS");assert.equal(result.tip,null);
});
test("quoted odds are reference only, never approved",()=>{
 const prices={O25:{odd:2.35,bookmaker:"Test book"}};
 const result=previewVerdict(future,model,prices,NOW);
 assert.equal(result.status,"OBSERVAR");
 assert.ok(result.adjusted>0);
 assert.ok(result.requirements.some(x=>x.key==="odds"&&!x.ready));
});
