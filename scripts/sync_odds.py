#!/usr/bin/env python3
"""Optional pre-match odds via API-Football. Never pretends live Betano prices.

If API_FOOTBALL_KEY is absent, writes a clearly empty feed. API-Football docs:
https://www.api-football.com/documentation_v3#tag/Odds-(Pre-Match)
"""
from datetime import datetime,timezone,timedelta
import json
import os
from pathlib import Path
import re
import urllib.parse
import urllib.request
import urllib.error

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/"data"/"market_odds.json"
NOW=datetime.now(timezone.utc)
KEY=os.environ.get("API_FOOTBALL_KEY","").strip()
GROUPS=[
 ("1X2",{"1X2_H","1X2_D","1X2_A"}),
 ("O15",{"O15","U15"}),
 ("O25",{"O25","U25"}),
 ("BTTS",{"BTTS_Y","BTTS_N"})
]
def get(url):
    req=urllib.request.Request(url,headers={"x-apisports-key":KEY,"Accept":"application/json","User-Agent":"EDGY-Betting/1.1"})
    try:
        with urllib.request.urlopen(req,timeout=12) as response:
            return json.load(response)
    except (urllib.error.URLError,TimeoutError,ValueError) as exc:
        print("Odds provider error:",str(exc)[:120])
        return None
def key_for(bet,value):
    bet=str(bet).strip().casefold()
    value=str(value).strip().casefold()
    if bet in ("match winner","1x2","fulltime result","full time result","winner"):
        return {"home":"1X2_H","1":"1X2_H","draw":"1X2_D","x":"1X2_D","away":"1X2_A","2":"1X2_A"}.get(value)
    if bet in ("goals over/under","goals over under","over/under","total goals","total - over/under","total - over / under"):
        match=re.search(r"(over|under)\s*(1[.,]5|2[.,]5)",value)
        if match:
            return ("O" if match.group(1)=="over" else "U")+match.group(2).replace(",","").replace(".","")
    if bet in ("both teams score","both teams to score","btts","both teams to score (btts)"):
        return {"yes":"BTTS_Y","no":"BTTS_N"}.get(value)
    return None
def valid_price(value):
    try:
        number=float(value)
        return number if 1.01<=number<=1000 else None
    except (TypeError,ValueError):
        return None
def decode_event(event):
    rows={}
    for book in event.get("bookmakers") or []:
        name=str(book.get("name") or "Desconhecido").strip()
        if not name:
            continue
        prices={}
        for bet in book.get("bets") or []:
            betname=bet.get("name")
            for opt in bet.get("values") or []:
                key=key_for(betname,opt.get("value"))
                price=valid_price(opt.get("odd"))
                if key and price:
                    prices[key]=price
        rows[name]=prices
    all_keys=set(k for p in rows.values() for k in p)
    consolidated={}
    for outcome in all_keys:
        available=[]
        for bookmaker,prices in rows.items():
            if outcome not in prices:
                continue
            group=next((g for g,keys in GROUPS if outcome in keys),None)
            cohort=next((keys for g,keys in GROUPS if g==group),set())
            fair=None
            if cohort.issubset(prices.keys()):
                norm=sum(1/prices[k] for k in cohort)
                fair=round((1/prices[outcome])/norm,6) if norm else None
            available.append({"bookmaker":bookmaker,"odd":prices[outcome],"fairProbability":fair})
        if not available:
            continue
        preferred=next((x for x in available if "betano" in x["bookmaker"].casefold()),None)
        selected=preferred or max(available,key=lambda x:x["odd"])
        consolidated[outcome]={
            "odd":selected["odd"],"bookmaker":selected["bookmaker"],
            "source":"API-Football / bookmaker reportado",
            "betanoInFeed":bool(preferred),
            "betanoConfirmedOnSlip":False,
            "fairProbability":selected["fairProbability"],
            "availableBookmakers":len(available),
            "quotes":available[:12]}
    return consolidated
def main():
    payload={"generatedAt":NOW.isoformat(),"source":"API-Football (opcional; preços de referência, não confirmados no boletim)",
       "hasCredentials":bool(KEY),"matches":{},"message":"Sem API_FOOTBALL_KEY configurada: as odds não foram recolhidas."}
    if KEY:
        matches={}
        # 2 days, max 3 pages/day (<=6 API requests per sync)
        for offset in range(2):
            target=(NOW+timedelta(days=offset)).date().isoformat()
            for page in range(1,4):
                args=urllib.parse.urlencode({"date":target,"page":page})
                data=get("https://v3.football.api-sports.io/odds?"+args)
                if not isinstance(data,dict):
                    break
                if data.get("errors"):
                    payload["message"]="API-Football devolveu um erro ou a conta atingiu o limite."
                    break
                for event in data.get("response") or []:
                    fixture=event.get("fixture") or {}
                    fixtureid=fixture.get("id")
                    if fixtureid is None:
                        continue
                    decoded=decode_event(event)
                    if decoded:
                        matches["apif-"+str(fixtureid)]=decoded
                paging=data.get("paging") or {}
                if not data.get("response") or int(paging.get("current") or page)>=int(paging.get("total") or page):
                    break
        payload["matches"]=matches
        if not payload["message"].startswith("API-Football"):
            payload["message"]="Odds indicativas; confirmar sempre na Betano antes da decisão."
    if DEST.exists():
        try:
            old=json.loads(DEST.read_text(encoding="utf-8"))
            if old.get("matches")==payload["matches"] and old.get("hasCredentials")==payload["hasCredentials"]:
                print("Odds unchanged")
                return
        except (OSError,ValueError):
            pass
    DEST.parent.mkdir(exist_ok=True)
    DEST.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Odds events:",len(payload["matches"]))
if __name__=="__main__":
    main()
