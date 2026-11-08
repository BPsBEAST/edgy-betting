import test from "node:test";
import assert from "node:assert/strict";
import {evaluate} from "../src/engine.js";
const base={
 matchId:"fixture-123",day:"2026-11-08",market:"result",selection:"Vitória equipa da casa",
 odds:2,priceSource:"betano",probabilities:{fair:80,statarea:78,sporty:77},
 bank:100,weeklyLoss:0,maxPerDay:3,minOdds:1.3,maxOdds:5,prudence:1
};
test("missing probabilities never approve a bet",()=>assert.equal(evaluate({...base,probabilities:{}}).status,"OBSERVAR"));
test("two independent sources and positive prudent edge can qualify",()=>{
 const result=evaluate(base);
 assert.equal(result.status,"APOSTA");
 assert.ok(result.adjusted>=.03);
 assert.ok(result.stake>0&&result.stake<=1);
});
test("international/reference price must be verified",()=>assert.equal(evaluate({...base,priceSource:"reference"}).status,"VERIFICAR"));
test("strong rotation is a critical exclusion",()=>assert.equal(evaluate({...base,criticalRotation:true}).status,"EXCLUIDA"));
test("weather is a critical exclusion",()=>assert.equal(evaluate({...base,criticalWeather:true}).status,"EXCLUIDA"));
test("corners with ESPN only remain on watch",()=>assert.equal(evaluate({...base,market:"corners",probabilities:{espn:78}}).status,"OBSERVAR"));
test("two Statarea inputs are not two independent providers",()=>assert.equal(evaluate({...base,probabilities:{statarea:80,stataGoals:80}}).status,"OBSERVAR"));
test("weekly stop at minus three percent",()=>assert.equal(evaluate({...base,weeklyLoss:-3}).status,"OBSERVAR"));
test("odd range is enforced",()=>assert.equal(evaluate({...base,odds:10}).status,"OBSERVAR"));
test("two positions in one match block a third",()=>{
 const saved=[{matchId:base.matchId,group:"golos",day:base.day},{matchId:base.matchId,group:"remates",day:base.day}];
 assert.equal(evaluate(base,saved).status,"OBSERVAR");
});
test("correlated markets are blocked",()=>{
 assert.equal(evaluate(base,[{matchId:base.matchId,group:"resultado",day:base.day}]).status,"OBSERVAR");
});
test("majority negative fair-probability trend blocks qualification",()=>{
 const input={...base,bookmakers:[{name:"Betano",open:70,current:63},{name:"Betclic",open:69,current:61},{name:"bwin",open:68,current:67}]};
 assert.equal(evaluate(input).status,"OBSERVAR");
});
test("second division carries higher uncertainty",()=>{
 assert.ok(evaluate({...base,secondDivision:true}).uncertainty>evaluate(base).uncertainty);
});
test("stake never exceeds ten percent of prudent Kelly",()=>{
 const a=evaluate(base);assert.ok(a.stake<=a.kelly*.1*base.bank+1e-9);
});
test("void bets use win/push/loss settlement correctly",()=>{
 const input={...base,market:"void",odds:2.2,pushProbability:30,probabilities:{fair:45,statarea:45,sporty:45}};
 const a=evaluate(input);
 assert.ok(Math.abs(a.ev-(.45*1.2-.25))<1e-10);
 assert.ok(Math.abs(a.equivalent-.45/.7)<1e-10);
});
test("quarter asian lines never approve using the whole-win model",()=>assert.equal(evaluate({...base,market:"quarter"}).status,"OBSERVAR"));
