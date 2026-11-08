#!/usr/bin/env python3
"""Limited public ESPN soccer game summaries and confirmed starting lineups.

ESPN site API is an unofficial, no-key JSON feed. Do not bypass errors,
scrape HTML, or infer a lineup from an incomplete roster. Max 8 summaries
and 4 team injury reports per sync; availability varies by competition.
"""
from __future__ import annotations
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import urllib.request
import urllib.error
import urllib.parse

ROOT=Path(__file__).resolve().parents[1]
FIXTURES=ROOT/"data"/"fixtures.json"
DEST=ROOT/"data"/"espn_context.json"
NOW=datetime.now(timezone.utc)
MAX_SUMMARIES=8
MAX_INJURY_TEAMS=4
def load(path):
    try:return json.loads(path.read_text(encoding="utf-8"))
    except (OSError,ValueError):return {}
def parse_time(v):
    try:
        t=datetime.fromisoformat(str(v).replace("Z","+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    except (ValueError,TypeError):return None
def fetch(url):
    try:
        req=urllib.request.Request(url,headers={
          "Accept":"application/json","User-Agent":"EDGY-Betting/2.5 (limited ESPN public match summaries)"})
        with urllib.request.urlopen(req,timeout=10) as response:
            return json.load(response)
    except (OSError,ValueError,urllib.error.URLError) as exc:
        print("ESPN context unavailable:",str(exc)[:100]);return None
def valid_id(v):
    t=str(v or "")
    return t if t.isdigit() and 1<=len(t)<=15 else None
def read_lineups(data,game,now=NOW):
    kick=parse_time(game.get("utc"))
    if not kick or not 0<=(kick-now).total_seconds()<=2*3600:return None
    entries=data.get("rosters") if isinstance(data,dict) else None
    if not isinstance(entries,list) or len(entries)!=2:return None
    actual={}
    expected={str(game.get("homeId")):game.get("home"),str(game.get("awayId")):game.get("away")}
    for entry in entries:
        team=entry.get("team") or {}
        tid=str(team.get("id") or "")
        roster=entry.get("roster") or []
        if tid not in expected or not isinstance(roster,list):return None
        names=[]
        for item in roster:
            if item.get("starter") is not True:continue
            athlete=item.get("athlete") or {}
            name=str(athlete.get("displayName") or "").strip()
            if name:names.append(name[:90])
        if len(names)!=11 or len(set(names))!=11:return None
        actual[tid]={"team":expected[tid],"startingXI":names}
    if set(actual)!=set(expected):return None
    return {"provider":"ESPN (integração pública não oficial)","confirmed":True,
            "verifiedBy":"11 atletas marcados como starter para cada equipa no resumo do encontro, ≤2 horas antes",
            "teams":[actual[str(game["homeId"])],actual[str(game["awayId"])]]}
def extract_team_injuries(data,team):
    if not isinstance(data,dict):return None
    records=data.get("injuries")
    if not isinstance(records,list):return None
    entries=[]
    for item in records[:35]:
        athlete=item.get("athlete") or {}
        name=str(athlete.get("displayName") or athlete.get("name") or "").strip()
        if not name:continue
        raw_status=item.get("status") or ""
        st=raw_status.get("type") if isinstance(raw_status,dict) else raw_status
        entries.append({"name":name[:90],"team":str(team.get("name"))[:80],
          "status":str(st or "")[:50],
          "detail":str(item.get("details") or "")[:120]})
    return entries
def main():
    games=load(FIXTURES).get("games") or []
    upcoming=sorted([g for g in games if str(g.get("id","")).startswith("espn-") and
      (t:=parse_time(g.get("utc"))) and NOW<t<NOW+timedelta(days=4)],key=lambda g:g["utc"])
    contexts={}
    calls=0
    for g in upcoming[:MAX_SUMMARIES]:
        code=g.get("leagueCode")
        event=valid_id(str(g.get("id"))[5:])
        if not code or not event:continue
        url="https://site.api.espn.com/apis/site/v2/sports/soccer/"+urllib.parse.quote(code)+"/summary?event="+event
        data=fetch(url);calls+=1
        if not isinstance(data,dict):continue
        xi=read_lineups(data,g)
        if xi:contexts.setdefault(g["id"],{})["lineups"]=xi
        url_match="https://www.espn.com/soccer/match/_/gameId/"+event
        contexts.setdefault(g["id"],{})["matchPage"]=url_match
    unique={}
    for g in upcoming[:4]:
        for team,idkey in ((g.get("home"),g.get("homeId")),(g.get("away"),g.get("awayId"))):
            club=valid_id(idkey)
            if club and len(unique)<MAX_INJURY_TEAMS:
                unique.setdefault((g.get("leagueCode"),club),{"name":team,"club":club})
    injury_by_team={}
    for (league,club),team in unique.items():
        url="https://site.api.espn.com/apis/site/v2/sports/soccer/"+urllib.parse.quote(league)+"/teams/"+club+"/injuries"
        response=fetch(url);calls+=1
        records=extract_team_injuries(response,team)
        if records is not None:injury_by_team[(league,club)]=records
    for g in upcoming:
        league=g.get("leagueCode")
        home=injury_by_team.get((league,str(g.get("homeId"))))
        away=injury_by_team.get((league,str(g.get("awayId"))))
        if home is not None and away is not None:
            contexts.setdefault(g["id"],{})["injuries"]={"provider":"ESPN (integração pública não oficial)",
               "dataPresent":True,"players":home+away,"coverage":"Registos ESPN disponíveis, não substituem confirmação de todas as ausências"}
    output={"generatedAt":NOW.isoformat(),"provider":"ESPN site API pública, integração não oficial",
      "calls":calls,"matchedGames":len(contexts),
      "withLineups":sum(bool(x.get("lineups")) for x in contexts.values()),
      "withInjuries":sum(bool(x.get("injuries")) for x in contexts.values()),"contexts":contexts,
      "note":"Só se confirma XI ao encontrar 11 titulares identificados para cada equipa no resumo, nas 2h antes do jogo. Sem registo não significa que não existam ausências."}
    old=load(DEST)
    if old.get("contexts")==contexts:
        print("ESPN context unchanged;",len(contexts),"games");return
    DEST.parent.mkdir(exist_ok=True,parents=True)
    DEST.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("ESPN public match context:",len(contexts),"games,",output["withLineups"],"verified lineups,",calls,"API GETs")
if __name__=="__main__":main()
