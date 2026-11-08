#!/usr/bin/env python3
"""Source-aware pre-match context. Do not invent stadium coordinates or missing data.

Open-Meteo forecasts use a VERIFIED venue city from fixture providers, not team
name guesses; they are indicative city-level forecasts, not pitch forecasts.
API-Football context is optional and bounded for limited request quotas.
This script never classifies a bet as approved.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request
import urllib.error
import unicodedata

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/"data"/"context.json"
FIXTURES=ROOT/"data"/"fixtures.json"
NOW=datetime.now(timezone.utc)
API_KEY=os.environ.get("API_FOOTBALL_KEY","").strip()
MAX_API_CALLS=max(0,min(30,int(os.environ.get("API_FOOTBALL_CONTEXT_CALL_LIMIT","6"))))
COUNTRY={"Portugal":"PT","Inglaterra":"GB","Itália":"IT","Espanha":"ES","Alemanha":"DE","França":"FR"}
CALLS=0

def load(path):
    try:
        data=json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data,dict) else {}
    except (OSError,ValueError):
        return {}
def get(url,headers=None):
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"EDGYBetting/2.1 (+github.com/BPsBEAST/edgy-betting)","Accept":"application/json",**(headers or {})})
        with urllib.request.urlopen(req,timeout=12) as response:
            return json.load(response)
    except (urllib.error.URLError,TimeoutError,ValueError) as exc:
        print("Context source unavailable:",url.split("?")[0],str(exc)[:80])
        return None
def parse_time(value):
    try:
        value=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    except (ValueError,TypeError):return None
def normalize(name):
    text=unicodedata.normalize("NFKD",str(name or "").strip().casefold())
    return "".join(ch for ch in text if not unicodedata.combining(ch))
def country(game):
    return COUNTRY.get(str(game.get("league") or "").split(" · ")[0])
def geocode(city,code):
    args=urllib.parse.urlencode({"name":city,"count":5,"countryCode":code,"language":"en"})
    response=get("https://geocoding-api.open-meteo.com/v1/search?"+args)
    for place in (response or {}).get("results") or []:
        if place.get("country_code")!=code:continue
        if normalize(place.get("name"))!=normalize(city):continue
        lat,lon=place.get("latitude"),place.get("longitude")
        if isinstance(lat,(float,int)) and isinstance(lon,(float,int)):
            return lat,lon
    return None
def weather_forecast(lat,lon,when):
    args=urllib.parse.urlencode({
      "latitude":lat,"longitude":lon,"timezone":"UTC","forecast_days":16,
      "hourly":"precipitation,wind_gusts_10m,temperature_2m"})
    forecast=get("https://api.open-meteo.com/v1/forecast?"+args)
    hourly=(forecast or {}).get("hourly") or {}
    dates=hourly.get("time") or []
    target=when.astimezone(timezone.utc).replace(minute=0,second=0,microsecond=0).strftime("%Y-%m-%dT%H:%M")
    if target not in dates:return None
    idx=dates.index(target)
    def field(name):
        try:
            val=hourly[name][idx]
            return float(val) if val is not None else None
        except (KeyError,IndexError,TypeError,ValueError):return None
    rain=field("precipitation")
    gust=field("wind_gusts_10m")
    temp=field("temperature_2m")
    risk=bool((rain is not None and rain>=8) or (gust is not None and gust>=50))
    return {"temperatureC":temp,"precipitationMm":rain,"gustKmh":gust,
      "alert":risk,"risk":"Chuva intensa ou rajadas fortes previstas na zona urbana" if risk else None,
      "forecastHourUtc":target+"Z","provider":"Open-Meteo",
      "scope":"Aproximação por cidade; não representa condições verificadas no estádio."}
def apif_request(endpoint,fixture):
    global CALLS
    if CALLS>=MAX_API_CALLS or not API_KEY:return None
    CALLS+=1
    args=urllib.parse.urlencode({"fixture":fixture})
    raw=get("https://v3.football.api-sports.io/"+endpoint+"?"+args,{"x-apisports-key":API_KEY})
    if not isinstance(raw,dict) or raw.get("errors"):return None
    return raw.get("response")
def licensed_context(game):
    fixture=int(game["id"].removeprefix("apif-"))
    stamp=parse_time(game.get("utc"))
    output={}
    # API-Football predictions are their own named provider, NOT Statarea or SportyTrader.
    predictions=apif_request("predictions",fixture)
    if isinstance(predictions,list) and predictions:
        first=predictions[0]
        percentages=((first.get("predictions") or {}).get("percent") or {})
        percent={}
        for k,field in (("1X2_H","home"),("1X2_D","draw"),("1X2_A","away")):
            try:
                val=float(str(percentages.get(field,"")).replace("%",""))
                if 0<=val<=100:percent[k]=round(val/100,4)
            except (TypeError,ValueError):pass
        if percent:output["predictions"]={"provider":"API-Football","probabilities":percent,
          "advice":str((first.get("predictions") or {}).get("advice") or "")[:180]}
    injuries=apif_request("injuries",fixture)
    if isinstance(injuries,list):
        players=[]
        for entry in injuries[:30]:
            player=entry.get("player") or {}
            team=entry.get("team") or {}
            if not player.get("name"):continue
            players.append({"name":str(player["name"])[:85],"team":str(team.get("name") or "")[:75],
              "reason":str(player.get("reason") or "")[:100],"type":str(player.get("type") or "")[:70]})
        output["injuries"]={"provider":"API-Football","dataPresent":True,"players":players}
    # Actual team lists usually only appear close to kickoff.
    if stamp and 0<=(stamp-NOW).total_seconds()<=5400:
        lineups=apif_request("fixtures/lineups",fixture)
        if isinstance(lineups,list) and len(lineups)>=2:
            teams=[]
            for group in lineups:
                club=group.get("team") or {}
                players=[]
                for member in group.get("startXI") or []:
                    p=member.get("player") or {}
                    if p.get("name"):players.append(str(p["name"])[:90])
                if len(players)>=9:
                    teams.append({"team":str(club.get("name") or ""),"startingXI":players[:11]})
            if len(teams)==2:output["lineups"]={"provider":"API-Football","confirmed":True,"teams":teams}
    return output
def main():
    games=load(FIXTURES).get("games") or []
    upcoming=sorted((g for g in games if
       (t:=parse_time(g.get("utc"))) and NOW<t<=NOW+timedelta(days=9)),
       key=lambda g:g["utc"])
    contexts={}
    cities={}
    for g in upcoming:
        when=parse_time(g.get("utc"))
        city=str(g.get("venueCity") or "").strip()
        iso=country(g)
        if city and iso and len(city)<100:
            key=(city.casefold(),iso)
            if key not in cities and len(cities)<16:
                position=geocode(city,iso)
                cities[key]={"coords":position}
            position=(cities.get(key) or {}).get("coords")
            if position:
                # Cache one forecast per city per fixture-hour.
                cachekey=key+(when.strftime("%Y-%m-%dT%H"),)
                if cachekey not in forecast_cache:
                    forecast_cache[cachekey]=weather_forecast(*position,when)
                weather=forecast_cache[cachekey]
                if weather:contexts.setdefault(g["id"],{})["weather"]={"city":city,"countryCode":iso,**weather}
    # Respect low API request budgets: focus only on the nearest licensed fixtures.
    for g in upcoming:
        if CALLS>=MAX_API_CALLS:break
        if str(g.get("id","")).startswith("apif-"):
            info=licensed_context(g)
            if info:contexts.setdefault(g["id"],{}).update(info)
    output={"generatedAt":NOW.isoformat(),"sources":{"weather":"Open-Meteo (requires verified venue city)",
      "lineups":"API-Football optional","injuries":"API-Football optional",
      "predictions":"API-Football optional (distinct from Statarea/SportyTrader)",
      "soccernews":"not connected","statarea":"not connected","sportytrader":"not connected",
      "soccervital":"not connected"},
      "hasApiFootballKey":bool(API_KEY),"apiCalls":CALLS,
      "matchedGames":len(contexts),"contexts":contexts,
      "message":"Missing data is reported as unavailable. No automatic critical exclusion without confirmed match-specific evidence."}
    old=load(DEST)
    if old.get("contexts")==output["contexts"] and old.get("hasApiFootballKey")==output["hasApiFootballKey"]:
        print("No context changes",len(contexts),"matches",CALLS,"API calls")
        return
    DEST.parent.mkdir(parents=True,exist_ok=True)
    DEST.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Context available",len(contexts),"matches",CALLS,"API calls")
forecast_cache={}
if __name__=="__main__":
    main()
