#!/usr/bin/env python3
"""Match odds with ESPN fixtures using strict, explicitly unverified metadata.

Free API-Football plan denies fixture-by-IDs and the current 2026/27 season.
Never claim team identity is verified from league/time metadata alone.
This script makes ZERO additional authenticated provider requests.
"""
from __future__ import annotations
from datetime import datetime, timezone
from difflib import SequenceMatcher
import json
import os
from pathlib import Path
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
FIXTURE_FILE=ROOT/"data"/"fixtures.json"
ODDS_FILE=ROOT/"data"/"market_odds.json"
API_KEY=os.environ.get("API_FOOTBALL_KEY","").strip()
API_LEAGUES={
 94:"por.1",95:"por.2",39:"eng.1",40:"eng.2",
 135:"ita.1",136:"ita.2",140:"esp.1",141:"esp.2",
 78:"ger.1",79:"ger.2",61:"fra.1",62:"fra.2",
 2:"uefa.champions",3:"uefa.europa",848:"uefa.europa.conf",
 45:"eng.fa",48:"eng.league_cup",143:"esp.copa_del_rey",
 137:"ita.coppa_italia",81:"ger.dfb_pokal",66:"fra.coupe_de_france",
 96:"por.taca.portugal"
}
ALIASES={
 "man utd":"manchester united","man united":"manchester united",
 "man city":"manchester city","inter":"inter milan",
 "internazionale":"inter milan","milan":"ac milan",
 "psg":"paris saint germain","paris sg":"paris saint germain",
 "wolves":"wolverhampton wanderers","spurs":"tottenham hotspur",
 "vitoria de guimaraes":"vitoria guimaraes",
 "vitoria guimaraes":"vitoria guimaraes","sporting cp":"sporting lisbon",
 "porto":"porto"
}
def norm(value):
    cleaned=unicodedata.normalize("NFKD",str(value or "").casefold())
    cleaned="".join(ch for ch in cleaned if not unicodedata.combining(ch))
    cleaned=re.sub(r"[^a-z0-9]+"," ",cleaned)
    cleaned=re.sub(r"\b(fc|cf|sc|ac|tsg|football|club|de|do|da|04|1909)\b"," ",cleaned)
    cleaned=" ".join(cleaned.split())
    return ALIASES.get(cleaned,cleaned)

def similarity(a,b):
    x,y=norm(a),norm(b)
    return SequenceMatcher(None,x,y).ratio() if x and y else 0

def iso(value):
    try:
        dt=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError,TypeError):return None

def match_fixture(api,calendar):
    fixture=api.get("fixture") or {}
    league=api.get("league") or {}
    teams=api.get("teams") or {}
    homes=teams.get("home") or {}
    aways=teams.get("away") or {}
    t=iso(fixture.get("date"))
    try:expected=API_LEAGUES.get(int(league.get("id")))
    except (ValueError,TypeError):expected=None
    if not t or not expected or not homes.get("name") or not aways.get("name"):return None
    candidates=[]
    for game in calendar:
        # Only same competition, kickoff +/- 90 minutes and BOTH teams.
        # TheSportsDB has a different leagueCode but identical league label.
        name_code=game.get("leagueCode")
        if name_code!=expected:
            continue
        kickoff=iso(game.get("utc"))
        if kickoff is None or abs((t-kickoff).total_seconds())>90*60:continue
        score1=similarity(homes["name"],game.get("home"))
        score2=similarity(aways["name"],game.get("away"))
        if min(score1,score2)<.78:continue
        candidates.append(((score1+score2)/2,game["id"]))
    candidates.sort(reverse=True)
    if not candidates:return None
    if len(candidates)>1 and candidates[0][0]-candidates[1][0]<.10:return None
    return candidates[0][1]

def api_get(ids):
    args=urllib.parse.urlencode({"ids":"-".join(str(i) for i in ids)})
    url="https://v3.football.api-sports.io/fixtures?"+args
    request=urllib.request.Request(url,headers={"x-apisports-key":API_KEY,
        "Accept":"application/json","User-Agent":"EDGY-Betting/2.2"})
    try:
        with urllib.request.urlopen(request,timeout=18) as response:
            data=json.load(response)
        if data.get("errors"):
            print("Link provider error:",str(data["errors"])[:150]);return []
        return data.get("response") or []
    except (OSError,TimeoutError,urllib.error.URLError,ValueError) as exc:
        print("Link provider unavailable:",str(exc)[:100]);return []


def match_metadata(metadata,calendar):
    """Provisional correspondence only: unique league and exact start time.

    Odds response contains no team names, so this is NOT an identity-verified
    match and must never be promoted into an approved bet.
    """
    if not isinstance(metadata,dict):return None
    try:league_code=API_LEAGUES.get(int(metadata.get("leagueId")))
    except (ValueError,TypeError):return None
    kickoff=iso(metadata.get("utc"))
    if not kickoff or not league_code:return None
    candidates=[]
    for game in calendar:
        if game.get("leagueCode")!=league_code:continue
        game_time=iso(game.get("utc"))
        if game_time and abs((game_time-kickoff).total_seconds())<=300:
            candidates.append(game["id"])
    return candidates[0] if len(candidates)==1 else None

def main():
    if not API_KEY:return print("No API key configured; no odds to link")
    odds=json.loads(ODDS_FILE.read_text(encoding="utf-8"))
    fixtures=json.loads(FIXTURE_FILE.read_text(encoding="utf-8"))
    existing_matches=set((odds.get("matches") or {}).keys())
    metadata=odds.get("fixtureMetadata") or {}
    candidates={}
    # API-Football free plan does not support fixtures?ids and currently blocks
    # season 2026/27; do not waste API requests on a known forbidden endpoint.
    for external_id,meta in metadata.items():
        if external_id not in existing_matches:continue
        internal=match_metadata(meta,fixtures.get("games") or [])
        if internal:
            candidates.setdefault(internal,[]).append(external_id)
    provisional={internal:ids[0] for internal,ids in candidates.items() if len(ids)==1}
    old_verified=odds.get("linkedFixtureIds") or {}
    # Old verified IDs were produced by endpoints denied by the free plan.
    # Recompute only if a separately authorized identity-verified feed exists.
    verified={}
    odds["linkedFixtureIds"]=verified
    odds["linkedFixtureCount"]=0
    odds["provisionalFixtureIds"]=provisional
    odds["provisionalFixtureCount"]=len(provisional)
    odds["matchingMethod"]="Competição e hora de início únicas (±5 min); EQUIPAS NÃO VERIFICADAS"
    odds["linkStatus"]="provisional_only" if provisional else "unmatched"
    odds["lookupRequests"]=0
    odds["matchingCoverage"]={
       "oddsFixtureCount":len(existing_matches),
       "metadataCount":len(metadata),
       "metadataWithLeagueAndDate":sum(bool(m.get("leagueId") and m.get("utc")) for m in metadata.values()),
       "ambiguousKickoffs":sum(1 for ids in candidates.values() if len(ids)>1),
       "previousVerified":len(old_verified)
    }
    ODDS_FILE.write_text(json.dumps(odds,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Odds source:",len(existing_matches),"events;",len(metadata),"metadata;",
          len(provisional),"provisional date/league links;",0,"identity-verified links")
if __name__=="__main__":main()
