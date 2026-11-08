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
# Query only the competitions requested by the user; global date pagination
# mostly returned MLS, Nordic and other irrelevant leagues on this free plan.
TARGET_LEAGUES={
 "por.1":94,"por.2":95,"eng.1":39,"eng.2":40,
 "ita.1":135,"ita.2":136,"esp.1":140,"esp.2":141,
 "ger.1":78,"ger.2":79,"fra.1":61,"fra.2":62,
 "uefa.champions":2,"uefa.europa":3,"uefa.europa.conf":848,
 "eng.fa":45,"eng.league_cup":48,
 "esp.copa_del_rey":143,"ita.coppa_italia":137,
 "ger.dfb_pokal":81,"fra.coupe_de_france":66,
 "por.taca.portugal":96
}
def targeted_fixtures(limit=3):
    try:
        fixtures=json.loads((ROOT/"data"/"fixtures.json").read_text(encoding="utf-8")).get("games") or []
    except (ValueError,OSError):return []
    pairs={}
    for game in fixtures:
        league=TARGET_LEAGUES.get(game.get("leagueCode"))
        if not league:continue
        try:day=datetime.fromisoformat(str(game.get("utc")).replace("Z","+00:00")).astimezone(timezone.utc)
        except (ValueError,TypeError,AttributeError):continue
        if NOW<=day<=NOW+timedelta(days=7):
            k=(league,day.date().isoformat())
            pairs.setdefault(k,(day,game.get("leagueCode")))
    # The next three distinct leagues avoid wasting the daily quota on the
    # same competition. An error indicating plan restrictions stops all tests.
    picks=[]
    seen=set()
    for (league,date),(kickoff,code) in sorted(pairs.items(),key=lambda item:item[1][0]):
        if league in seen:continue
        picks.append({"league":league,"season":NOW.year if NOW.month>=7 else NOW.year-1,
                      "date":date,"code":code})
        seen.add(league)
        if len(picks)>=limit:break
    return picks

def main():
    payload={"generatedAt":NOW.isoformat(),"source":"API-Football (opcional; preços de referência, não confirmados no boletim)",
       "hasCredentials":bool(KEY),"matches":{},"message":"Sem API_FOOTBALL_KEY configurada: as odds não foram recolhidas."}
    if KEY:
        matches={}
        fixture_meta={}
        paging_info=[]
        days=max(1,min(7,int(os.environ.get("API_FOOTBALL_ODDS_DAYS","2"))))
        pages=max(1,min(25,int(os.environ.get("API_FOOTBALL_ODDS_MAX_PAGES","3"))))
        # Target the actual leagues and match dates from ESPN rather than
        # blindly collecting the first pages of unrelated world fixtures.
        max_targets=max(1,min(6,int(os.environ.get("API_FOOTBALL_ODDS_MAX_TARGETS","3"))))
        requests=targeted_fixtures(max_targets)
        provider_restrictions=[]
        for query in requests:
            for page in range(1,min(3,pages+1)):
                args=urllib.parse.urlencode({"league":query["league"],"season":query["season"],
                                             "date":query["date"],"page":page})
                data=get("https://v3.football.api-sports.io/odds?"+args)
                if not isinstance(data,dict):
                    provider_restrictions.append("Resposta de odds indisponível (API/rede).")
                    break
                if data.get("errors"):
                    reason=str(data["errors"])[:180]
                    provider_restrictions.append(reason)
                    print("Odds target blocked:",query["code"],reason)
                    break
                results=data.get("response") or []
                paging=data.get("paging") or {}
                paging_info.append({"date":query["date"],"leagueCode":query["code"],
                                    "page":page,"totalPages":paging.get("total"),"events":len(results)})
                for event in results:
                    fixture=event.get("fixture") or {}
                    fixtureid=fixture.get("id")
                    if fixtureid is None:continue
                    decoded=decode_event(event)
                    if not decoded:continue
                    matchkey="apif-"+str(fixtureid)
                    matches[matchkey]=decoded
                    lg=event.get("league") or {}
                    fixture_meta[matchkey]={
                      "utc":fixture.get("date"),"leagueId":lg.get("id"),
                      "leagueName":lg.get("name"),"leagueCountry":lg.get("country"),
                      "season":lg.get("season"),"utcTimestamp":fixture.get("timestamp")
                    }
                if not results or int(paging.get("current") or page)>=int(paging.get("total") or page):
                    break
            if provider_restrictions and ("free" in provider_restrictions[-1].lower() or
                                           "plan" in provider_restrictions[-1].lower()):
                break
        payload["targetedQueries"]=requests
        payload["providerRestrictions"]=provider_restrictions[:4]
        if provider_restrictions:
            payload["message"]="Cobertura de odds limitada pelo plano da API-Football; " + provider_restrictions[0]
        elif matches:
            payload["message"]="Odds de referência nas competições escolhidas; equipas e preço Betano por confirmar."
        else:
            payload["message"]="Nenhuma odd encontrada nas competições/datas consultadas (cobertura limitada)."
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
