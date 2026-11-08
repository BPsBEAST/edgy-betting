#!/usr/bin/env python3
"""Free, documented prediction APIs only. Never synthesize sources or approvals.

KiqIQ: https://kiqiq.com/api (CORS-open, no key; Poisson model).
Skorbot: https://skorbot.live/en/api/ (public read-only; attribution required).
These are NOT Statarea, SportyTrader, or SoccerVital. External providers may
have correlated inputs/methods and can be absent or stale.

No scraping, no authentication, no bypassing paywalls, max five HTTP calls.
"""
from __future__ import annotations
import datetime as dt
from difflib import SequenceMatcher
import json
from pathlib import Path
import re
import unicodedata
from urllib.request import Request, urlopen
from urllib.error import URLError

ROOT=Path(__file__).resolve().parents[1]
FIXTURES=ROOT/"data"/"fixtures.json"
DEST=ROOT/"data"/"free_predictions.json"
NOW=dt.datetime.now(dt.timezone.utc)
USER_AGENT="EDGY-Betting/2.3 (free, source-attributed fixture analytics; github.com/BPsBEAST/edgy-betting)"
SOURCE_MAX_AGE_H=48
COMPETITIONS={
    "premier league":"eng.1","english premier league":"eng.1",
    "championship":"eng.2","efl championship":"eng.2",
    "primeira liga":"por.1","liga portugal":"por.1",
    "serie a":"ita.1","serie b":"ita.2",
    "la liga":"esp.1","laliga":"esp.1",
    "segunda division":"esp.2","laliga 2":"esp.2",
    "bundesliga":"ger.1","2 bundesliga":"ger.2",
    "ligue 1":"fra.1","ligue 2":"fra.2","fransa ligue 2":"fra.2",
    "uefa champions league":"uefa.champions",
    "uefa europa league":"uefa.europa","uefa avrupa ligi":"uefa.europa",
    "uefa conference league":"uefa.europa.conf",
}
ALIASES={
    "man utd":"manchester united","man united":"manchester united",
    "man city":"manchester city","spurs":"tottenham hotspur",
    "tottenham":"tottenham hotspur","inter":"inter milan",
    "internazionale":"inter milan","milan":"ac milan",
    "athletic":"athletic club","athletic bilbao":"athletic club",
    "psg":"paris saint germain","paris sg":"paris saint germain",
    "porto":"porto","vitoria guimaraes":"vitoria guimaraes",
    "manchester utd":"manchester united",
    "gladbach":"borussia monchengladbach","bayern":"bayern munich",
    "leipzig":"rb leipzig","dortmund":"borussia dortmund",
    "forest":"nottingham forest"
}
def norm(value):
    val=unicodedata.normalize("NFKD",str(value or "").casefold())
    val="".join(ch for ch in val if not unicodedata.combining(ch))
    val=re.sub(r"[^a-z0-9]+"," ",val)
    val=re.sub(r"\b(fc|cf|afc|sc|ac|football|club|de|do|da)\b"," ",val)
    val=" ".join(val.split())
    return ALIASES.get(val,val)
def parse_time(value):
    try:
        x=dt.datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return x if x.tzinfo else x.replace(tzinfo=dt.timezone.utc)
    except (ValueError,TypeError):return None
def valid_prob(value):
    # Never accept a missing probability as 0.
    return type(value) in (int,float) and 0<=value<=1
def probabilities(raw):
    if not isinstance(raw,dict):return None
    arr=[raw.get(k) for k in ("home","draw","away")]
    if not all(map(valid_prob,arr)) or abs(sum(arr)-1)>.025:return None
    return {"1X2_H":round(arr[0],5),"1X2_D":round(arr[1],5),"1X2_A":round(arr[2],5)}
def league_code(name):
    return COMPETITIONS.get(norm(name))
def match(row,fixtures,now=NOW):
    t=parse_time(row.get("kickoff"))
    competition=league_code(row.get("competition"))
    home=norm(row.get("home"))
    away=norm(row.get("away"))
    if not t or not competition or not home or not away or t<=now:return None
    candidates=[]
    for f in fixtures:
        if f.get("leagueCode")!=competition:continue
        t2=parse_time(f.get("utc"))
        if not t2 or t2<=now or abs((t-t2).total_seconds())>30*60:continue
        h=norm(f.get("home"));a=norm(f.get("away"))
        sh=SequenceMatcher(None,home,h).ratio()
        sa=SequenceMatcher(None,away,a).ratio()
        if sh>=.84 and sa>=.84:candidates.append((min(sh,sa),f["id"]))
    if len(candidates)!=1:return None
    return candidates[0][1]
def fresh(value,now=NOW,max_age_hours=SOURCE_MAX_AGE_H):
    timestamp=parse_time(value)
    if not timestamp:return False
    age=(now-timestamp).total_seconds()
    return -300<=age<=max_age_hours*3600
def get_json(url):
    try:
        req=Request(url,headers={"User-Agent":USER_AGENT,"Accept":"application/json"})
        with urlopen(req,timeout=11) as response:
            body=response.read(2_000_000)
        value=json.loads(body.decode("utf-8"))
        return value if isinstance(value,dict) else None
    except (OSError,ValueError,UnicodeError,URLError) as exc:
        print("Free source unavailable:",url.split("?")[0],str(exc)[:130])
        return None
def read_json(path):
    try:return json.loads(path.read_text(encoding="utf-8"))
    except (OSError,ValueError):return {}
def sources_from_kiqiq(data,fixtures,now):
    if not data or not fresh(data.get("generated_at"),now):return {}, "Sem feed atualizado (máximo 48 h)"
    mapped={}
    for row in (data.get("fixtures") or [])[:100]:
        if not isinstance(row,dict):continue
        triplet=probabilities({"home":row.get("home_win_prob"),
                               "draw":row.get("draw_prob"),"away":row.get("away_win_prob")})
        if not triplet:continue
        gameid=match({"kickoff":row.get("kickoff_iso"),"competition":row.get("competition"),
                      "home":row.get("home"),"away":row.get("away")},fixtures,now)
        if not gameid:continue
        mapped[gameid]={"provider":"KiqIQ","updatedAt":data["generated_at"],
                        "method":"Poisson próprio do fornecedor (pode ter inputs correlacionados)",
                        "probabilities":triplet,
                        "sourceUrl":"https://kiqiq.com/api"}
    return mapped,"Disponível" if mapped else "Feed válido, sem correspondências seguras"
def sources_from_skorbot(data,fixtures,now):
    if not data or not fresh(data.get("generated_at"),now):return {}, "Feed indisponível ou expirado (máximo 48 h)"
    mapped={}
    for row in (data.get("matches") or [])[:250]:
        if not isinstance(row,dict) or row.get("status") not in ("scheduled","pre_match"):continue
        if not fresh(row.get("updated_at"),now):continue
        triplet=probabilities(row.get("probabilities"))
        if not triplet:continue
        gameid=match(row,fixtures,now)
        if not gameid:continue
        path=row.get("url")
        link="https://skorbot.live/en/api/"
        if isinstance(path,str) and re.fullmatch(r"/api/v1/matches/[a-zA-Z0-9-]+\.json",path):
            link="https://skorbot.live"+path
        mapped[gameid]={"provider":"Skorbot","updatedAt":row["updated_at"],
                        "method":"Previsão do modelo Skorbot (fonte externa identificada)",
                        "probabilities":triplet,"sourceUrl":link}
    return mapped,"Disponível" if mapped else "Feed válido, sem correspondências seguras"
def main():
    fixtures=[f for f in read_json(FIXTURES).get("games",[]) if parse_time(f.get("utc")) and parse_time(f.get("utc"))>NOW]
    kiqiq=get_json("https://kiqiq.com/api/v1/predictions?limit=100")
    skorbot=get_json("https://skorbot.live/api/v1/matches.json")
    first,status_k=sources_from_kiqiq(kiqiq,fixtures,NOW)
    second,status_s=sources_from_skorbot(skorbot,fixtures,NOW)
    matched={}
    for provider_map in (first,second):
        for gameid,record in provider_map.items():
            matched.setdefault(gameid,[]).append(record)
    payload={
        "generatedAt":NOW.isoformat(),"matches":matched,
        "matchedGames":len(matched),"withTwoSources":sum(len(s)>1 for s in matched.values()),
        "providers":{"KiqIQ":{"status":status_k,"matches":len(first),"url":"https://kiqiq.com/api"},
                     "Skorbot":{"status":status_s,"matches":len(second),"url":"https://skorbot.live/en/api/"}},
        "note":"APIs públicas e gratuitas; não substituem Statarea/SportyTrader nem garantem independência dos dados. Sem odds Betano e contexto não podem aprovar apostas."
    }
    old=read_json(DEST)
    if old.get("matches")==payload["matches"] and old.get("providers")==payload["providers"]:
        print("Free predictions unchanged",payload["matchedGames"],"matches");return
    DEST.parent.mkdir(parents=True,exist_ok=True)
    DEST.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Free predictions",payload["matchedGames"],"games;",payload["withTwoSources"],"with both external providers",status_k,status_s)
if __name__=="__main__":main()
