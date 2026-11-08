#!/usr/bin/env python3
"""EDGY Betting calendar sync. Public fixtures only; never makes bets.
ESPN site data is an unofficial integration; TheSportsDB is a limited fallback.
Optional API-FOOTBALL_KEY provides broader licensed coverage on supported plans.
"""
from __future__ import annotations
import datetime as dt
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT=pathlib.Path(__file__).resolve().parents[1]
DEST=ROOT/"data"/"fixtures.json"
TODAY=dt.datetime.now(dt.timezone.utc)
START=TODAY-dt.timedelta(days=1)
END=TODAY+dt.timedelta(days=10)
LOG=[]
# Best-effort league codes; an unsupported league returns zero games, not fake fixtures.
LEAGUES=[
 ("por.1","Portugal · Primeira Liga",1),("por.2","Portugal · Liga 2",2),
 ("eng.1","Inglaterra · Premier League",1),("eng.2","Inglaterra · Championship",2),
 ("ita.1","Itália · Serie A",1),("ita.2","Itália · Serie B",2),
 ("esp.1","Espanha · La Liga",1),("esp.2","Espanha · Segunda División",2),
 ("ger.1","Alemanha · Bundesliga",1),("ger.2","Alemanha · 2. Bundesliga",2),
 ("fra.1","França · Ligue 1",1),("fra.2","França · Ligue 2",2),
 ("uefa.champions","UEFA · Champions League",1),
 ("uefa.europa","UEFA · Europa League",1),
 ("uefa.europa.conf","UEFA · Conference League",1),
 ("uefa.super_cup","UEFA · Supertaça Europeia",1),
 ("eng.fa","Inglaterra · FA Cup",1),("eng.league_cup","Inglaterra · League Cup",1),
 ("esp.copa_del_rey","Espanha · Copa del Rey",1),("ita.coppa_italia","Itália · Coppa Italia",1),
 ("ger.dfb_pokal","Alemanha · DFB-Pokal",1),("fra.coupe_de_france","França · Coupe de France",1),
 ("por.taca_de_portugal","Portugal · Taça de Portugal",1)
]
TSDB=[
 ("4328","Inglaterra · Premier League",1),("4329","Inglaterra · Championship",2),
 ("4331","Alemanha · Bundesliga",1),("4332","Itália · Serie A",1),
 ("4334","França · Ligue 1",1),("4335","Espanha · La Liga",1),
]
# API-Football numeric IDs, if enabled by repository secret.
APILEAGUES=[
 (94,"Portugal · Primeira Liga",1),(95,"Portugal · Liga 2",2),
 (39,"Inglaterra · Premier League",1),(40,"Inglaterra · Championship",2),
 (135,"Itália · Serie A",1),(136,"Itália · Serie B",2),
 (140,"Espanha · La Liga",1),(141,"Espanha · Segunda División",2),
 (78,"Alemanha · Bundesliga",1),(79,"Alemanha · 2. Bundesliga",2),
 (61,"França · Ligue 1",1),(62,"França · Ligue 2",2),
 (2,"UEFA · Champions League",1),(3,"UEFA · Europa League",1),(848,"UEFA · Conference League",1),
 (45,"Inglaterra · FA Cup",1),(48,"Inglaterra · League Cup",1),
 (143,"Espanha · Copa del Rey",1),(137,"Itália · Coppa Italia",1),
 (81,"Alemanha · DFB-Pokal",1),(66,"França · Coupe de France",1),
 (96,"Portugal · Taça de Portugal",1)
]
def get_json(url,headers=None):
    req=urllib.request.Request(url,headers={"User-Agent":"EDGYBetting/1.0 (+github.com/BPsBEAST/edgy-betting)","Accept":"application/json",**(headers or {})})
    try:
        with urllib.request.urlopen(req,timeout=12) as resp:
            return json.load(resp)
    except (urllib.error.URLError,TimeoutError,ValueError,UnicodeError) as exc:
        LOG.append(f"{url.split('?')[0].split('/')[-1]}: {str(exc)[:100]}")
        return None

def iso(value):
    if not value:return None
    try:
        parsed=dt.datetime.fromisoformat(str(value).replace("Z","+00:00"))
        if parsed.tzinfo is None:parsed=parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc).isoformat().replace("+00:00","Z")
    except ValueError:return None

def eligible(item):
    if not item or not item.get("utc") or not item.get("home") or not item.get("away"):return False
    stamp=dt.datetime.fromisoformat(item["utc"].replace("Z","+00:00"))
    return START<=stamp<=END

def espn():
    result=[]
    a=START.strftime("%Y%m%d")
    b=END.strftime("%Y%m%d")
    for slug,name,division in LEAGUES:
        url=f"https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/scoreboard?dates={a}-{b}&limit=250"
        response=get_json(url)
        if not isinstance(response,dict):continue
        for event in response.get("events") or []:
            comp=(event.get("competitions") or [{}])[0]
            team_list=comp.get("competitors") or []
            home=next((t for t in team_list if t.get("homeAway")=="home"),{})
            away=next((t for t in team_list if t.get("homeAway")=="away"),{})
            if not home or not away:continue
            hteam=home.get("team") or {}
            ateam=away.get("team") or {}
            stamp=iso(event.get("date") or comp.get("date"))
            rawstatus=(event.get("status") or {}).get("type") or {}
            score=lambda x: (int(x["score"]) if str(x.get("score","")).isdigit() else None)
            item={"id":"espn-"+str(event.get("id")),"home":hteam.get("displayName") or hteam.get("name"),"away":ateam.get("displayName") or ateam.get("name"),
                "league":name,"leagueCode":slug,"division":division,"utc":stamp,"status":rawstatus.get("abbreviation") or rawstatus.get("name") or "NS",
                "homeScore":score(home),"awayScore":score(away),"homeLogo":hteam.get("logo"),"awayLogo":ateam.get("logo"),
                "source":"ESPN"}
            if eligible(item):result.append(item)
        time.sleep(.08)
    return result

def thesportsdb():
    result=[]
    for lid,name,division in TSDB:
        url="https://www.thesportsdb.com/api/v1/json/123/eventsnextleague.php?id="+lid
        data=get_json(url)
        for event in (data or {}).get("events") or []:
            raw=event.get("strTimestamp")
            timestamp=iso(raw) if raw else iso(str(event.get("dateEvent") or "")+"T"+str(event.get("strTime") or "12:00:00"))
            item={"id":"tsdb-"+str(event.get("idEvent")),"home":event.get("strHomeTeam"),"away":event.get("strAwayTeam"),
                  "league":name,"leagueCode":"tsdb-"+lid,"division":division,"utc":timestamp,"status":event.get("strStatus") or "NS",
                  "homeScore":event.get("intHomeScore"),"awayScore":event.get("intAwayScore"),
                  "homeLogo":event.get("strHomeTeamBadge"),"awayLogo":event.get("strAwayTeamBadge"),"source":"TheSportsDB"}
            if eligible(item):result.append(item)
        time.sleep(.08)
    return result

def api_football(key):
    result=[]
    headers={"x-apisports-key":key}
    season=TODAY.year if TODAY.month>=7 else TODAY.year-1
    for league,name,division in APILEAGUES:
        args=urllib.parse.urlencode({"league":league,"season":season,"from":TODAY.strftime("%Y-%m-%d"),"to":END.strftime("%Y-%m-%d")})
        data=get_json("https://v3.football.api-sports.io/fixtures?"+args,headers)
        if not isinstance(data,dict):continue
        if data.get("errors"):LOG.append("API-Football "+str(league)+": "+str(data["errors"])[:100]);continue
        for row in data.get("response") or []:
            fixture=row.get("fixture") or {};teams=row.get("teams") or {};goals=row.get("goals") or {};home=teams.get("home") or {};away=teams.get("away") or {}
            item={"id":"apif-"+str(fixture.get("id")),"home":home.get("name"),"away":away.get("name"),
              "league":name,"leagueCode":"apif-"+str(league),"division":division,"utc":iso(fixture.get("date")),
              "status":(fixture.get("status") or {}).get("short") or "NS","homeScore":goals.get("home"),"awayScore":goals.get("away"),
              "homeLogo":home.get("logo"),"awayLogo":away.get("logo"),"source":"API-Football"}
            if eligible(item):result.append(item)
        time.sleep(.15)
    return result

def main():
    all_matches=[]
    source_names=[]
    key=os.environ.get("API_FOOTBALL_KEY","").strip()
    if key:
        rows=api_football(key);all_matches.extend(rows)
        if rows:source_names.append("API-Football")
    # ESPN supplements regions/competitions not available via plan.
    rows=espn()
    all_matches.extend(rows)
    if rows:source_names.append("ESPN (integração não oficial)")
    rows=thesportsdb()
    all_matches.extend(rows)
    if rows:source_names.append("TheSportsDB (plano gratuito limitado)")
    # Prefer API-Football > ESPN > TheSportsDB for the same teams and calendar date.
    seen=set()
    priority={"API-Football":0,"ESPN":1,"TheSportsDB":2}
    clean=[]
    for x in sorted(all_matches,key=lambda x:priority.get(x.get("source"),9)):
        # Team naming can differ between providers; exact dedup is conservative.
        key=(x["utc"][:10],x["home"].casefold().replace(" fc","").replace(" cf","").strip(),x["away"].casefold().replace(" fc","").replace(" cf","").strip())
        if key in seen:continue
        seen.add(key);clean.append(x)
    clean.sort(key=lambda x:x["utc"])
    if DEST.exists():
        try:old=json.loads(DEST.read_text())
        except (ValueError,OSError):old={}
    else:old={}
    # If the upstream goes down, keep recent cached data, but mark it stale.
    if not clean and old.get("games"):
        print("No feed returned fixtures; preserving existing cache.")
        return
    result={"generatedAt":TODAY.isoformat().replace("+00:00","Z"),"sources":source_names,"games":clean,
        "message":"" if clean else "Os fornecedores ainda não disponibilizaram jogos para o período. A cobertura gratuita é limitada.",
        "notes":["Jogos reais de fornecedores identificados","Sem probabilidades, odds ou apostas automáticas"]}
    DEST.parent.mkdir(parents=True,exist_ok=True)
    # Avoid needless commits for timestamp-only changes if fixture data has not changed.
    if old.get("games")==result["games"] and old.get("sources")==result["sources"]:
        print(f"No fixture changes ({len(clean)} matches).")
        return
    DEST.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Updated {len(clean)} fixtures from {', '.join(source_names) or 'no source'}.")
    if LOG:print("Non-fatal feed warnings:", "; ".join(LOG[:6]),file=sys.stderr)
if __name__=="__main__":main()
