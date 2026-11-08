#!/usr/bin/env python3
"""Collect real ESPN match histories and calculate exploratory Poisson probabilities.

This does NOT produce verified betting tips. Official user rules require two
independent named prediction sources and a Betano price; those inputs are absent
unless expressly integrated. No fabricated data, odds or lineups.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import time
import urllib.request
import urllib.error

ROOT=Path(__file__).resolve().parents[1]
FIXTURES=ROOT/"data"/"fixtures.json"
FORM=ROOT/"data"/"team_form.json"
OUTPUT=ROOT/"data"/"analysis.json"
NOW=datetime.now(timezone.utc)
STALE_HOURS=24
MAX_TEAMS=90
USER_AGENT="EDGY-Betting/1.1 (public project, aggregated match results)"
MAX_HISTORY=18
MODEL_MIN_GAMES=5
MAX_EVENTS=8
SOURCE="ESPN (histórico não oficial)"
WARNINGS=[]

def read_json(path, default):
    try:
        data=json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data,dict) else default
    except (OSError,ValueError):
        return default

def write_json(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    content=json.dumps(value,ensure_ascii=False,indent=2,sort_keys=False)+"\n"
    # Preserve a stable generated timestamp when content is unchanged.
    if path.exists():
        old=read_json(path,{})
        new=dict(value)
        if {k:v for k,v in old.items() if k!="generatedAt"}=={k:v for k,v in new.items() if k!="generatedAt"}:
            print("No changes:",path.name)
            return
    path.write_text(content,encoding="utf-8")
    print("Updated",path.name)

def parsedate(value):
    try:
        v=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    except (ValueError,TypeError):
        return None

def get_json(url):
    try:
        req=urllib.request.Request(url,headers={"User-Agent":USER_AGENT,"Accept":"application/json"})
        with urllib.request.urlopen(req,timeout=10) as resp:
            return json.load(resp)
    except (urllib.error.URLError,TimeoutError,ValueError,UnicodeError) as error:
        return {"_error":str(error)[:100]}

def score(number):
    try:
        if isinstance(number,dict):
            number=number.get("value") or number.get("displayValue")
        if isinstance(number,(int,float,str)) and str(number).strip().isdigit():
            return int(number)
        return None
    except (ValueError,TypeError):
        return None

def completed(event):
    status=(event.get("status") or {}).get("type") or {}
    return bool(status.get("completed")) or status.get("name") in ("STATUS_FULL_TIME","STATUS_FINAL") or status.get("abbreviation") in ("FT","AET")

def event_to_record(event,teamid):
    if not completed(event):
        return None
    date=parsedate(event.get("date"))
    if not date or date>=NOW:
        return None
    games=event.get("competitions") or []
    if not games:
        return None
    participants=games[0].get("competitors") or []
    if len(participants)<2:
        return None
    team=next((p for p in participants if str((p.get("team") or {}).get("id") or p.get("id"))==str(teamid)),None)
    if team is None:
        return None
    opponent=next((p for p in participants if p is not team),None)
    if opponent is None:
        return None
    own=score(team.get("score"))
    other=score(opponent.get("score"))
    if own is None or other is None:
        return None
    side=team.get("homeAway")
    if side not in ("home","away"):
        return None
    return {"date":date.isoformat(),"side":side,"scored":own,"conceded":other}

def fetch_team(item):
    slug,tid=item
    # ESPN season year is normally the start of the current season.
    season=NOW.year if NOW.month>=7 else NOW.year-1
    url=f"https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/teams/{tid}/schedule?season={season}"
    raw=get_json(url)
    if raw.get("_error"):
        return item,{"fetchedAt":NOW.isoformat(),"matches":[],"error":raw["_error"]}
    games=raw.get("events") or []
    rows=[rec for event in games if (rec:=event_to_record(event,tid))]
    rows.sort(key=lambda r:r["date"],reverse=True)
    return item,{"fetchedAt":NOW.isoformat(),"matches":rows[:MAX_HISTORY],"error":None}

def enough_form(rows):
    recent=rows[:12]
    h=[m for m in recent if m["side"]=="home"]
    a=[m for m in recent if m["side"]=="away"]
    return len(recent)>=MODEL_MIN_GAMES and len(h)>=2 and len(a)>=2

def calculate_rates(rows):
    recent=rows[:12]
    if not enough_form(recent):
        return None
    home=[m for m in recent if m["side"]=="home"][:6]
    away=[m for m in recent if m["side"]=="away"][:6]
    def avg(arr,key):
        return sum(m[key] for m in arr)/len(arr)
    return {"games":len(recent),"homeGames":len(home),"awayGames":len(away),
      "homeFor":avg(home,"scored"),"homeAgainst":avg(home,"conceded"),
      "awayFor":avg(away,"scored"),"awayAgainst":avg(away,"conceded"),
      "allFor":avg(recent,"scored"),"allAgainst":avg(recent,"conceded")}

def poisson(lam,k):
    return math.exp(-lam)*(lam**k)/math.factorial(k)

def project(home,away,division):
    # Shrink observed side splits towards each team's own overall form, not
    # towards invented goals, and weight recent team scoring/defence equally.
    def shrink(side,allrate,n):
        weight=min(.8,n/(n+2))
        return weight*side+(1-weight)*allrate
    hf=shrink(home["homeFor"],home["allFor"],home["homeGames"])
    ha=shrink(home["homeAgainst"],home["allAgainst"],home["homeGames"])
    af=shrink(away["awayFor"],away["allFor"],away["awayGames"])
    aa=shrink(away["awayAgainst"],away["allAgainst"],away["awayGames"])
    lh=max(.15,min(4.5,(hf+aa)/2))
    la=max(.15,min(4.5,(af+ha)/2))
    grid=[(x,y,poisson(lh,x)*poisson(la,y)) for x in range(MAX_EVENTS+1) for y in range(MAX_EVENTS+1)]
    total=sum(z for x,y,z in grid)
    probs={(x,y):z/total for x,y,z in grid}
    def prob(fn):
        return sum(p for (h,a),p in probs.items() if fn(h,a))
    available=[
       ("1X2_H","Resultado","Vitória casa",prob(lambda h,a:h>a),.035),
       ("1X2_D","Resultado","Empate",prob(lambda h,a:h==a),.045),
       ("1X2_A","Resultado","Vitória fora",prob(lambda h,a:h<a),.035),
       ("O15","Golos","Mais de 1,5 golos",prob(lambda h,a:h+a>1.5),.035),
       ("U15","Golos","Menos de 1,5 golos",prob(lambda h,a:h+a<1.5),.035),
       ("O25","Golos","Mais de 2,5 golos",prob(lambda h,a:h+a>2.5),.04),
       ("U25","Golos","Menos de 2,5 golos",prob(lambda h,a:h+a<2.5),.04),
       ("BTTS_Y","Golos","Ambas marcam — Sim",prob(lambda h,a:h>=1 and a>=1),.045),
       ("BTTS_N","Golos","Ambas marcam — Não",prob(lambda h,a:h==0 or a==0),.045)
    ]
    best=sorted(probs.items(),key=lambda pair:pair[1],reverse=True)[:2]
    for (h,a),p in best:
        available.append((f"CS_{h}_{a}","Resultado exato",f"Resultado exato {h}-{a}",p,.09))
    markets=[]
    low_samples=min(home["homeGames"],away["awayGames"])
    # Explicit model uncertainty, not a statistically calibrated confidence interval.
    extra=max(.015,.065-math.sqrt(low_samples)*.01)
    for key,group,label,p,difficulty in available:
        unc=(difficulty+extra)*(1.1 if division==2 else 1.0)
        min_target=p-unc-.03
        minodd=math.ceil((1/min_target)*100)/100 if min_target>.01 else None
        markets.append({"key":key,"group":group,"label":label,"probability":round(p,5),
          "uncertainty":round(unc,5),"minimumOdd":minodd,"status":"OBSERVAR",
          "reason":"Modelo estatístico ESPN sem duas fontes independentes e sem odd Betano confirmada."})
    return {"lambdaHome":round(lh,3),"lambdaAway":round(la,3),
      "home":{"sample":home["games"],"homeGames":home["homeGames"],"awayGames":home["awayGames"],
       "goalsForHome":round(home["homeFor"],2),"goalsAgainstHome":round(home["homeAgainst"],2)},
      "away":{"sample":away["games"],"homeGames":away["homeGames"],"awayGames":away["awayGames"],
       "goalsForAway":round(away["awayFor"],2),"goalsAgainstAway":round(away["awayAgainst"],2)},
      "model":"Poisson exploratório sobre resultados anteriores; não representa xG oficial nem prognóstico calibrado.",
      "sources":[SOURCE],"markets":markets}

def main():
    fixture_data=read_json(FIXTURES,{})
    fixtures=fixture_data.get("games") or []
    upcoming=[g for g in fixtures if g.get("source")=="ESPN" and parsedate(g.get("utc")) and
      NOW<=parsedate(g["utc"])<=NOW+timedelta(days=10) and g.get("homeId") and g.get("awayId")]
    upcoming.sort(key=lambda g:g["utc"])
    unique=[]
    seen=set()
    for g in upcoming:
        for tid in (g["homeId"],g["awayId"]):
            entry=(g["leagueCode"],str(tid))
            if entry not in seen and len(unique)<MAX_TEAMS:
                unique.append(entry);seen.add(entry)
    cache=read_json(FORM,{"teams":{}})
    cache_entries=cache.get("teams") if isinstance(cache.get("teams"),dict) else {}
    def cachekey(item):
        return item[0]+":"+item[1]
    def is_fresh(item):
        entry=cache_entries.get(cachekey(item),{})
        when=parsedate(entry.get("fetchedAt"))
        return when and when>NOW-timedelta(hours=STALE_HOURS) and bool(entry.get("matches"))
    missing=[item for item in unique if not is_fresh(item)]
    with ThreadPoolExecutor(max_workers=5) as pool:
        tasks=[pool.submit(fetch_team,item) for item in missing]
        for future in as_completed(tasks):
            item,team_data=future.result()
            cache_entries[cachekey(item)]=team_data
    write_json(FORM,{"generatedAt":NOW.isoformat(),"teams":cache_entries})
    result={}
    for game in upcoming:
        home=cache_entries.get(cachekey((game["leagueCode"],str(game["homeId"]))),{})
        away=cache_entries.get(cachekey((game["leagueCode"],str(game["awayId"]))),{})
        hs=calculate_rates(home.get("matches") or [])
        ats=calculate_rates(away.get("matches") or [])
        if hs and ats:
            result[game["id"]]=project(hs,ats,game.get("division",1))
    output={
      "generatedAt":NOW.isoformat(),"source":"ESPN — histórico de jogos; integração não oficial",
      "fixtureGeneratedAt":fixture_data.get("generatedAt"),
      "count":len(result),"coverage":len(upcoming),"models":result,
      "method":"Médias de golos dos últimos 12 jogos de cada equipa, separadas por casa/fora; Poisson exploratório. SEM confirmação de odds ou outras fontes.",
      "message":"Uma projeção estatística ESPN não cumpre sozinha as regras de consenso de apostas."
    }
    write_json(OUTPUT,output)
    print(f"Statistical models: {len(result)}/{len(upcoming)} ESPN fixtures; refreshed schedules: {len(missing)}")
if __name__=="__main__":
    main()
