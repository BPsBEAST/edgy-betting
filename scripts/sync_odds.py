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
 ("BTTS",{"BTTS_Y","BTTS_N"}),
 ("HT",{"HT_H","HT_D","HT_A"})
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
    bet=str(bet or "").strip().casefold()
    value=str(value or "").strip().casefold()
    home={"home":"H","1":"H","draw":"D","x":"D","away":"A","2":"A"}.get(value)
    if bet in ("match winner","1x2","fulltime result","full time result","winner"):
        return "1X2_"+home if home else None
    if bet in ("first half winner","1st half winner","half time result","halftime result","1st half - 1x2"):
        return "HT_"+home if home else None
    if bet in ("draw no bet","draw no bet (dnb)","draw no bet - fulltime") and value in ("home","away","1","2"):
        return "DNB_"+home
    # Half-time, team and corner totals are entirely different markets.
    # Never pass them off as full-match goals (the API contains many variants).
    if (("over/under" in bet or "over under" in bet or bet=="total goals")
        and not any(term in bet for term in
          ("half","1st","2nd","first","second","corner","booking","card","team","home","away","asian","minute","period"))):
        operation=re.search(r"^(over|under)\b",value)
        line=re.search(r"([1-4][.,]5)",value) or re.search(r"([1-4][.,]5)",bet)
        if operation and line:
            return ("O" if operation.group(1)=="over" else "U")+line.group(1).replace(",","").replace(".","")
    if bet in ("both teams score","both teams to score","btts","both teams to score (btts)"):
        return {"yes":"BTTS_Y","no":"BTTS_N"}.get(value)
    if bet in ("correct score","correct score - fulltime","exact score","fulltime correct score"):
        match=re.fullmatch(r"(\d{1,2})\s*[-:]\s*(\d{1,2})",value)
        if match:return "CS_"+match.group(1)+"_"+match.group(2)
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
    for outcome in sorted(all_keys):
        available=[]
        for bookmaker,prices in rows.items():
            if outcome not in prices:
                continue
            group=next((g for g,keys in GROUPS if outcome in keys),None)
            cohort=next((keys for g,keys in GROUPS if g==group),set())
            fair=None
            if cohort and cohort.issubset(prices.keys()):
                norm=sum(1/prices[k] for k in cohort)
                fair=round((1/prices[outcome])/norm,6) if norm>0 else None
            available.append({"bookmaker":bookmaker,"odd":prices[outcome],"fairProbability":fair})
        if not available:
            continue
        preferred=next((x for x in available if "betano" in x["bookmaker"].casefold()),None)
        selected=preferred or max(available,key=lambda x:x["odd"])
        fairvalues=[x["fairProbability"] for x in available if isinstance(x["fairProbability"],float)]
        consensus=round(sum(fairvalues)/len(fairvalues),6) if len(fairvalues)>=2 else None
        consolidated[outcome]={
            "odd":selected["odd"],"bookmaker":selected["bookmaker"],
            "source":"API-Football / bookmaker reportado",
            "betanoInFeed":bool(preferred),
            "betanoConfirmedOnSlip":False,
            "fairProbability":selected["fairProbability"],
            "fairMarketConsensus":consensus,
            "fairBooks":len(fairvalues),
            "availableBookmakers":len(available),
            "quotes":available[:18]}
    return consolidated
def main():
    payload={"generatedAt":NOW.isoformat(),"source":"API-Football (opcional; preços de referência, não confirmados no boletim)",
       "hasCredentials":bool(KEY),"matches":{},"message":"Sem API_FOOTBALL_KEY configurada: as odds não foram recolhidas."}
    if KEY:
        matches={}
        fixture_meta={}
        paging_info=[]
        days=max(1,min(7,int(os.environ.get("API_FOOTBALL_ODDS_DAYS","2"))))
        pages=max(1,min(25,int(os.environ.get("API_FOOTBALL_ODDS_MAX_PAGES","3"))))
        # 2 days, max 3 pages/day (<=6 API requests per sync)
        for offset in range(days):
            target=(NOW+timedelta(days=offset)).date().isoformat()
            for page in range(1,pages+1):
                args=urllib.parse.urlencode({"date":target,"page":page})
                data=get("https://v3.football.api-sports.io/odds?"+args)
                if not isinstance(data,dict):
                    break
                if data.get("errors"):
                    payload["message"]="API-Football devolveu um erro ou a conta atingiu o limite."
                    break
                paging=data.get("paging") or {}
                paging_info.append({"date":target,"page":page,"totalPages":paging.get("total"),"events":len(data.get("response") or [])})
                for event in data.get("response") or []:
                    fixture=event.get("fixture") or {}
                    fixtureid=fixture.get("id")
                    if fixtureid is None:
                        continue
                    decoded=decode_event(event)
                    if decoded:
                        matchkey="apif-"+str(fixtureid)
                        matches[matchkey]=decoded
                        lg=event.get("league") or {}
                        fixture_meta[matchkey]={
                          "utc":fixture.get("date"),"leagueId":lg.get("id"),
                          "leagueName":lg.get("name"),"leagueCountry":lg.get("country"),
                          "season":lg.get("season"),"utcTimestamp":fixture.get("timestamp")
                        }
                paging=data.get("paging") or {}
                if not data.get("response") or int(paging.get("current") or page)>=int(paging.get("total") or page):
                    break
        old_data={}
        if DEST.exists():
            try:old_data=json.loads(DEST.read_text(encoding="utf-8"))
            except (ValueError,OSError):pass
        prior=old_data.get("matches") or {}
        for fixture,outcomes in matches.items():
            for market,item in outcomes.items():
                previous=(prior.get(fixture) or {}).get(market) or {}
                history=list(previous.get("snapshots") or [])
                if not history and previous.get("odd"):
                    history=[{"at":old_data.get("generatedAt"),"bookmaker":previous.get("bookmaker"),
                              "odd":previous["odd"],"fairProbability":previous.get("fairProbability")}]
                if not history or history[-1].get("odd")!=item["odd"] or history[-1].get("bookmaker")!=item["bookmaker"]:
                    history.append({"at":NOW.isoformat(),"bookmaker":item["bookmaker"],
                      "odd":item["odd"],"fairProbability":item.get("fairProbability")})
                item["snapshots"]=history[-12:]
        payload["matches"]=matches
        payload["fixtureMetadata"]=fixture_meta
        payload["pagesFetched"]=paging_info
        if not payload["message"].startswith("API-Football"):
            payload["message"]="Odds indicativas; confirmar sempre na Betano antes da decisão."
    if DEST.exists():
        try:
            old=json.loads(DEST.read_text(encoding="utf-8"))
            if old.get("matches")==payload["matches"] and old.get("fixtureMetadata")==payload.get("fixtureMetadata") and old.get("hasCredentials")==payload["hasCredentials"] and old.get("pagesFetched")==payload.get("pagesFetched"):
                print("Odds unchanged")
                return
        except (OSError,ValueError):
            pass
    DEST.parent.mkdir(exist_ok=True)
    DEST.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Odds events:",len(payload["matches"]))
if __name__=="__main__":
    main()
