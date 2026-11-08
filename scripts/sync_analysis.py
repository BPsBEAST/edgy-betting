#!/usr/bin/env python3
"""Create provisional statistics from published 2026/27 Football-Data CSVs.

Only actual settled match results, never made-up fixtures, odds, xG or tips.
Every preview must remain OBSERVAR until independent predictions and a verified
Betano price fulfil all the user's conditions.
"""
from __future__ import annotations
import csv
from datetime import datetime,timezone
from difflib import SequenceMatcher
from io import StringIO
import json
import math
from pathlib import Path
import re
import unicodedata
from urllib.request import Request,urlopen
from urllib.error import URLError

ROOT=Path(__file__).resolve().parents[1]
FIXTURES=ROOT/"data"/"fixtures.json"
DEST=ROOT/"data"/"analysis.json"
NOW=datetime.now(timezone.utc)
SOURCE="Football-Data.co.uk — resultados CSV publicados"
MAX_EVENTS=8
DIVISIONS={
 "por.1":"P1","eng.1":"E0","eng.2":"E1","ita.1":"I1","ita.2":"I2",
 "esp.1":"SP1","esp.2":"SP2","ger.1":"D1","ger.2":"D2",
 "fra.1":"F1","fra.2":"F2"
}
NAMES={
 "man united":"manchester united","man city":"manchester city",
 "nottm forest":"nottingham forest","wolves":"wolverhampton wanderers",
 "spurs":"tottenham","newcastle":"newcastle united",
 "ath madrid":"atletico madrid","atl madrid":"atletico madrid",
 "sociedad":"real sociedad","betis":"real betis",
 "ath bilbao":"athletic club","athletic bilbao":"athletic club",
 "vallecano":"rayo vallecano","celta":"celta vigo",
 "alaves":"deportivo alaves","cadiz":"cadiz",
 "paris sg":"paris saint germain","psg":"paris saint germain",
 "inter":"inter milan","internazionale":"inter milan",
 "milan":"ac milan","verona":"hellas verona",
 "bayern munich":"bayern munchen","bayern":"bayern munchen",
 "dortmund":"borussia dortmund","mgladbach":"borussia monchengladbach",
 "leverkusen":"bayer leverkusen","frankfurt":"eintracht frankfurt",
 "fc porto":"porto","sporting cp":"sporting lisbon",
 "sporting":"sporting lisbon","sp lisbon":"sporting lisbon",
 "vitoria guimaraes":"vitoria sc","guimaraes":"vitoria sc",
 "famalicao":"famalicao","santa clara":"santa clara"
}
def normalize(name):
    s=unicodedata.normalize("NFKD",str(name or ""))
    s="".join(c for c in s if not unicodedata.combining(c))
    s=s.casefold().replace("&","and")
    s=re.sub(r"[^a-z0-9]+"," ",s)
    s=re.sub(r"\b(fc|cf|afc|football|club|de|do|da|the|fk|sc|ac|calcio|sad)\b"," ",s)
    s=" ".join(s.split())
    return NAMES.get(s,s)
def read_json(path):
    try:return json.loads(path.read_text(encoding="utf-8"))
    except (OSError,ValueError):return {}
def download(div):
    season=f"{NOW.year%100:02d}{(NOW.year+1)%100:02d}" if NOW.month>=7 else f"{(NOW.year-1)%100:02d}{NOW.year%100:02d}"
    url=f"https://www.football-data.co.uk/mmz4281/{season}/{div}.csv"
    try:
        req=Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; EDGY-Betting; research)","Accept":"text/csv,*/*"})
        with urlopen(req,timeout=18) as response:
            raw=response.read(2_000_000).decode("utf-8-sig",errors="replace")
        rows=list(csv.DictReader(StringIO(raw)))
        return [r for r in rows if r.get("HomeTeam") and r.get("AwayTeam") and str(r.get("FTHG","")).strip().isdigit() and str(r.get("FTAG","")).strip().isdigit()]
    except (OSError,URLError,ValueError) as exc:
        print("CSV failed",div,str(exc)[:100])
        return []
def parse_date(value):
    text=str(value or "").strip()
    for fmt in ("%d/%m/%Y","%d/%m/%y","%Y-%m-%d"):
        try:return datetime.strptime(text,fmt).replace(tzinfo=timezone.utc)
        except ValueError:pass
    return None
def team_match(requested,names):
    n=normalize(requested)
    if not n:return None
    exact=[t for t in names if normalize(t)==n]
    if len(exact)==1:return exact[0]
    # Conservative fuzzy matching avoids accidentally assigning another club's results.
    scores=sorted(((SequenceMatcher(None,n,normalize(t)).ratio(),t) for t in names),reverse=True)
    if not scores:return None
    best=scores[0]
    second=scores[1][0] if len(scores)>1 else 0
    if best[0]>=.79 and best[0]-second>=.075:return best[1]
    return None
def form_for(team,rows):
    results=[]
    for r in rows:
        h=r["HomeTeam"];a=r["AwayTeam"]
        if team==h:
            side="home";scored=int(r["FTHG"]);conceded=int(r["FTAG"])
        elif team==a:
            side="away";scored=int(r["FTAG"]);conceded=int(r["FTHG"])
        else:continue
        date=parse_date(r.get("Date"))
        if not date or date>=NOW:continue
        results.append({"date":date.isoformat(),"side":side,"scored":scored,"conceded":conceded})
    results.sort(key=lambda r:r["date"],reverse=True)
    return results[:12]
def calculate_rates(rows):
    recent=rows[:12]
    home=[m for m in recent if m["side"]=="home"][:6]
    away=[m for m in recent if m["side"]=="away"][:6]
    if len(recent)<5 or len(home)<2 or len(away)<2:return None
    def avg(records,key):return sum(m[key] for m in records)/len(records)
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
    data=read_json(FIXTURES)
    games=data.get("games") or []
    divisions=set()
    for game in games:
        code=DIVISIONS.get(game.get("leagueCode"))
        if code:divisions.add(code)
    leagues={}
    for div in sorted(divisions):
        rows=download(div)
        if rows:leagues[div]=rows
    models={}
    unmatched=set()
    coverage=0
    for game in games:
        div=DIVISIONS.get(game.get("leagueCode"))
        rows=leagues.get(div)
        if not rows:continue
        dt=datetime.fromisoformat(str(game.get("utc","")).replace("Z","+00:00")) if game.get("utc") else NOW
        if not NOW<=dt or dt>NOW.replace(hour=0,minute=0,second=0,microsecond=0)+__import__("datetime").timedelta(days=11):
            continue
        coverage+=1
        names={r["HomeTeam"] for r in rows}|{r["AwayTeam"] for r in rows}
        ht=team_match(game.get("home"),names)
        at=team_match(game.get("away"),names)
        if not ht or not at or ht==at:
            unmatched.add(f"{game.get('home')} vs {game.get('away')} ({div})")
            continue
        home=calculate_rates(form_for(ht,rows))
        away=calculate_rates(form_for(at,rows))
        if not home or not away:continue
        result=project(home,away,game.get("division",1))
        result["sources"]=[SOURCE]
        result["sourceDate"]=max(str(r.get("Date") or "") for r in rows)
        models[game["id"]]=result
    payload={
      "generatedAt":NOW.isoformat(),"source":SOURCE,"fixtureGeneratedAt":data.get("generatedAt"),
      "count":len(models),"coverage":coverage,"models":models,
      "method":"Resultados da época corrente via CSV; 12 jogos recentes (casa/fora), modelo de Poisson exploratório com parâmetros não calibrados.",
      "message":"Projeção auxiliar. Não substitui a média ponderada da Statarea/SportyTrader, as odds justas ou as verificações contextuais.",
      "csvLeagues":sorted(leagues),"unmatchedTeams":len(unmatched)
    }
    if DEST.exists():
        old=read_json(DEST)
        if old.get("models")==payload["models"] and old.get("csvLeagues")==payload["csvLeagues"]:
            print("No changes in automatic model")
            return
    DEST.parent.mkdir(parents=True,exist_ok=True)
    DEST.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Models {len(models)}/{coverage}; leagues {len(leagues)}; unmatched {len(unmatched)}")
    if unmatched:print("Unmatched examples:",", ".join(sorted(unmatched)[:8]))
if __name__=="__main__":main()
