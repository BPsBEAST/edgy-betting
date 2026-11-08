#!/usr/bin/env python3
"""Free optional odds provider, current season; no paywall bypass.

The Odds API: https://the-odds-api.com/ (500 free credits / month).
Two leagues per run, EU region, two markets -> at most four credits per run.
At four daily runs this stays within 496 credits per 31-day month.
Only explicitly identified teams, same competition and kickoff get prices.
BETANO UK IS NOT BETANO PORTUGAL; never mark on-slip confirmation.
"""
from __future__ import annotations
from datetime import datetime,timezone,timedelta
import importlib.util
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request
import urllib.error

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/"data"/"free_odds.json"
FIXTURES=ROOT/"data"/"fixtures.json"
KEY=os.environ.get("THE_ODDS_API_KEY","").strip()
NOW=datetime.now(timezone.utc)
SPORTS={
"por.1":("soccer_portugal_primeira_liga","Primeira Liga"),
"eng.1":("soccer_epl","Premier League"),
"eng.2":("soccer_efl_champ","Championship"),
"ita.1":("soccer_italy_serie_a","Serie A"),
"ita.2":("soccer_italy_serie_b","Serie B"),
"esp.1":("soccer_spain_la_liga","La Liga"),
"esp.2":("soccer_spain_segunda_division","Segunda Division"),
"ger.1":("soccer_germany_bundesliga","Bundesliga"),
"ger.2":("soccer_germany_bundesliga2","2 Bundesliga"),
"fra.1":("soccer_france_ligue_one","Ligue 1"),
"fra.2":("soccer_france_ligue_two","Ligue 2"),
"uefa.champions":("soccer_uefa_champs_league","UEFA Champions League"),
"uefa.europa":("soccer_uefa_europa_league","UEFA Europa League"),
"uefa.europa.conf":("soccer_uefa_europa_conference_league","UEFA Conference League"),
"eng.fa":("soccer_fa_cup","FA Cup"),
"eng.league_cup":("soccer_england_efl_cup","EFL Cup"),
"esp.copa_del_rey":("soccer_spain_copa_del_rey","Copa del Rey"),
"ita.coppa_italia":("soccer_italy_coppa_italia","Coppa Italia"),
"ger.dfb_pokal":("soccer_germany_dfb_pokal","DFB Pokal"),
"fra.coupe_de_france":("soccer_france_coupe_de_france","Coupe de France")
}
spec=importlib.util.spec_from_file_location("free_pred",ROOT/"scripts"/"sync_free_predictions.py")
free_pred=importlib.util.module_from_spec(spec);spec.loader.exec_module(free_pred)
def valid_odd(val):
    return type(val) in (int,float) and 1.01<=val<=200
def read_json(path):
    try:return json.loads(path.read_text(encoding="utf-8"))
    except (OSError,ValueError):return {}
def parse_event(event,fixtures,sport):
    if not isinstance(event,dict):return None
    if sport not in SPORTS:return None
    game_id=free_pred.match({
      "competition":SPORTS[sport][1],"kickoff":event.get("commence_time"),
      "home":event.get("home_team"),"away":event.get("away_team")},fixtures,NOW)
    if not game_id:return None
    values={}
    for book in event.get("bookmakers") or []:
        bookmaker=str(book.get("title") or "").strip()[:75]
        if not bookmaker:continue
        prices={}
        updated=book.get("last_update")
        for market in book.get("markets") or []:
            key=market.get("key")
            for out in market.get("outcomes") or []:
                val=out.get("price")
                if not valid_odd(val):continue
                name=str(out.get("name") or "")
                if key=="h2h":
                    if name==event.get("home_team"):outcome="1X2_H"
                    elif name==event.get("away_team"):outcome="1X2_A"
                    elif name.lower()=="draw":outcome="1X2_D"
                    else:continue
                elif key=="totals":
                    try:line=float(out.get("point"))
                    except (TypeError,ValueError):continue
                    if line not in (1.5,2.5,3.5):continue
                    if name=="Over":outcome="O"+str(int(line*10))
                    elif name=="Under":outcome="U"+str(int(line*10))
                    else:continue
                else:continue
                prices[outcome]={"odd":float(val),"updatedAt":updated}
        if prices:values[bookmaker]=prices
    groups=[{"1X2_H","1X2_D","1X2_A"},{"O15","U15"},{"O25","U25"},{"O35","U35"}]
    consolidated={}
    for outcome in {x for book in values.values() for x in book}:
        available=[]
        cohort=next((g for g in groups if outcome in g),set())
        for bookmaker,books in values.items():
            if outcome not in books:continue
            norm=sum(1/books[k]["odd"] for k in cohort if k in books)
            fair=((1/books[outcome]["odd"])/norm if cohort.issubset(books) and norm>0 else None)
            available.append({"bookmaker":bookmaker,"odd":books[outcome]["odd"],
                              "fairProbability":round(fair,5) if fair is not None else None,
                              "updatedAt":books[outcome].get("updatedAt")})
        if not available:continue
        prefer=next((x for x in available if "betano" in x["bookmaker"].lower()),None)
        # International prices are ALWAYS references, even if named Betano.
        selected=prefer or max(available,key=lambda x:x["odd"])
        fairvals=[x["fairProbability"] for x in available if isinstance(x["fairProbability"],float)]
        consolidated[outcome]={
            "odd":selected["odd"],"bookmaker":selected["bookmaker"],
            "source":"The Odds API (free, preço internacional)",
            "betanoInFeed":bool(prefer),"betanoConfirmedOnSlip":False,
            "fairProbability":selected["fairProbability"],
            "fairMarketConsensus":round(sum(fairvals)/len(fairvals),5) if len(fairvals)>=2 else None,
            "fairBooks":len(fairvals),"availableBookmakers":len(available),
            "quotes":available[:15],"verifiedTeams":True,"updatedAt":selected["updatedAt"]}
    return (game_id,consolidated) if consolidated else None
def next_sports(fixtures,count=2):
    upcoming=[g for g in fixtures if (t:=free_pred.parse_time(g.get("utc"))) and NOW<t<=NOW+timedelta(days=6)]
    byleague={}
    for g in upcoming:
        code=g.get("leagueCode")
        if code in SPORTS: byleague.setdefault(code,free_pred.parse_time(g["utc"]))
    pairs=sorted(byleague.items(),key=lambda pair:pair[1])
    # Choose a different pair on each of the 4 daily runs; monthly <=496 credits.
    offset=(NOW.hour//6*2)%(len(pairs) or 1)
    ordered=pairs[offset:]+pairs[:offset]
    return [code for code,_ in ordered[:count]]
def main():
    payload={"generatedAt":NOW.isoformat(),"source":"The Odds API — gratuito opcional",
             "hasCredentials":bool(KEY),"matches":{},"sportsRequested":[],
             "costBudgetCreditsPerRun":4,
             "message":"Para odds internacionais atuais, acrescentar THE_ODDS_API_KEY (plano gratuito)."}
    if KEY:
        fixtures=read_json(FIXTURES).get("games") or []
        sports=next_sports(fixtures)
        payload["sportsRequested"]=sports
        seen=set()
        errors=[]
        for sport in sports:
            sportkey,_=SPORTS[sport]
            query=urllib.parse.urlencode({"apiKey":KEY,"regions":"eu","markets":"h2h,totals","oddsFormat":"decimal","dateFormat":"iso"})
            url=f"https://api.the-odds-api.com/v4/sports/{sportkey}/odds/?"+query
            request=urllib.request.Request(url,headers={"User-Agent":"EDGY-Betting/2.3","Accept":"application/json"})
            try:
                with urllib.request.urlopen(request,timeout=13) as response:
                    records=json.load(response)
                    remaining=response.headers.get("x-requests-remaining")
                    if remaining is not None:payload["creditsRemaining"]=remaining
            except (OSError,ValueError,urllib.error.URLError) as exc:
                errors.append(f"{sport}: {str(exc)[:100]}")
                continue
            if not isinstance(records,list):continue
            for event in records:
                parsed=parse_event(event,fixtures,sport)
                if not parsed:continue
                game_id,quotes=parsed
                if game_id in seen:continue
                seen.add(game_id)
                payload["matches"][game_id]=quotes
        payload["errors"]=errors[:5]
        payload["message"]="Odds internacionais de referência, não preços Betano Portugal. Verificar no boletim."
    old=read_json(DEST)
    if old.get("matches")==payload["matches"] and old.get("hasCredentials")==payload["hasCredentials"]:
        print("Free odds unchanged");return
    DEST.parent.mkdir(parents=True,exist_ok=True)
    DEST.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("The Odds API",len(payload["matches"]),"verified matches from",len(payload["sportsRequested"]),"competitions; key",bool(KEY))
if __name__=="__main__":main()
