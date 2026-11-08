#!/usr/bin/env python3
"""Free pre-match bookmaker odds from Football-Data.co.uk's published CSV.

Only attaches quotes after matching BOTH team names, division and kickoff time.
Published snapshots are NOT live Betano Portugal prices. Zero credentials.
Source: https://www.football-data.co.uk/matches/fixtures.csv
"""
from __future__ import annotations
import csv
from datetime import datetime, timedelta, timezone
from io import StringIO
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.request import Request,urlopen
from urllib.error import URLError

import sync_analysis as analysis

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/"data"/"football_data_odds.json"
FIXTURES=ROOT/"data"/"fixtures.json"
NOW=datetime.now(timezone.utc)
LONDON=ZoneInfo("Europe/London")
CODES={value:key for key,value in analysis.DIVISIONS.items()}
# Open bookmaker-specific triplets only; never treat maximum/average composite
# prices as one bookmaker's coherent 1X2 market.
BOOKS={
  "B365":"Bet365","BW":"bwin","WH":"William Hill","PS":"Pinnacle",
  "BF":"Betfair","BFD":"Betfred","BV":"BetVictor","PP":"Paddy Power"
}
COLUMNS={"1X2_H":"H","1X2_D":"D","1X2_A":"A"}
TOTAL_BOOKS={"B365":"Bet365","P":"Pinnacle"}
GROUPS=({"1X2_H","1X2_D","1X2_A"},{"O25","U25"})
URLS=[
 "https://www.football-data.co.uk/matches/fixtures.csv",
 "https://www.football-data.co.uk/fixtures.csv"
]
def read(path):
    try:return json.loads(path.read_text(encoding="utf-8"))
    except (OSError,ValueError):return {}
def number(value):
    try:
        x=float(str(value or "").strip())
        return x if math.isfinite(x) and 1.01<=x<=200 else None
    except (TypeError,ValueError):return None
def kickoff(row):
    date=str(row.get("Date") or "").strip()
    hour=str(row.get("Time") or "").strip()
    if not hour:return None
    for fmt in ("%d/%m/%Y %H:%M","%d/%m/%y %H:%M","%d/%m/%Y %H:%M:%S",
                "%Y-%m-%d %H:%M"):
        try:return datetime.strptime(date+" "+hour,fmt).replace(tzinfo=LONDON).astimezone(timezone.utc)
        except ValueError:continue
    return None
def fixture_for(row,games,now=NOW):
    code=CODES.get(str(row.get("Div") or "").strip())
    dt=kickoff(row)
    home=str(row.get("HomeTeam") or "").strip()
    away=str(row.get("AwayTeam") or "").strip()
    if not code or not dt or not home or not away or dt<=now or dt>now+timedelta(days=8):
        return None
    same_time=[g for g in games if g.get("leagueCode")==code and
        (other:=analysis_dt(g.get("utc"))) and abs((dt-other).total_seconds())<=45*60]
    if not same_time:return None
    names={g["home"] for g in same_time}|{g["away"] for g in same_time}
    h=analysis.team_match(home,names)
    a=analysis.team_match(away,names)
    if not h or not a or h==a:return None
    candidates=[g for g in same_time if g["home"]==h and g["away"]==a]
    return candidates[0]["id"] if len(candidates)==1 else None
def analysis_dt(value):
    try:
        dt=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError,ValueError):return None
def bookmaker_prices(row):
    prices={}
    for prefix,bookname in BOOKS.items():
        selection={}
        for key,token in COLUMNS.items():
            price=number(row.get(prefix+token))
            if price is not None:selection[key]=price
        if len(selection)==3:prices[bookname]=selection
    for prefix,bookname in TOTAL_BOOKS.items():
        over=number(row.get(prefix+">2.5"))
        under=number(row.get(prefix+"<2.5"))
        if over and under:
            prices.setdefault(bookname,{})
            prices[bookname].update({"O25":over,"U25":under})
    return prices
def decode(row):
    bybook=bookmaker_prices(row)
    consolidated={}
    for market in sorted({m for book in bybook.values() for m in book}):
        group=next((g for g in GROUPS if market in g),set())
        quotes=[]
        for bookname,bookprices in bybook.items():
            if market not in bookprices or not group.issubset(bookprices):continue
            margin=sum(1/bookprices[k] for k in group)
            if not .85<=margin<=1.5:continue
            quotes.append({"bookmaker":bookname,"odd":bookprices[market],
                "fairProbability":round(1/bookprices[market]/margin,6)})
        if not quotes:continue
        # Best price is one verified international BOOKMAKER price, not MaxH.
        best=max(quotes,key=lambda item:item["odd"])
        fair=[item["fairProbability"] for item in quotes]
        consolidated[market]={
            "odd":best["odd"],"bookmaker":best["bookmaker"],"source":"Football-Data.co.uk — fixtures.csv",
            "betanoInFeed":False,"betanoConfirmedOnSlip":False,"verifiedTeams":True,
            "fairProbability":best["fairProbability"],
            "fairMarketConsensus":round(sum(fair)/len(fair),6) if len(fair)>=2 else None,
            "fairBooks":len(fair),"availableBookmakers":len(quotes),"quotes":quotes[:12],
            "priceCategory":"published-reference-not-live"}
    return consolidated
def download():
    for url in URLS:
        try:
            req=Request(url,headers={"Accept":"text/csv,text/plain,*/*",
              "User-Agent":"EDGY-Betting/2.4 (public football-data CSV research)"})
            with urlopen(req,timeout=16) as response:
                data=response.read(2_000_000).decode("utf-8-sig",errors="replace")
            rows=list(csv.DictReader(StringIO(data)))
            if rows and all(key in rows[0] for key in ("Div","Date","HomeTeam","AwayTeam")):
                return rows,url
            print("Invalid fixture CSV (missing required fields) from",url)
        except (URLError,OSError,ValueError) as exc:
            print("Football-Data fixture download failed:",str(exc)[:100])
    return [],None
def main():
    games=read(FIXTURES).get("games") or []
    rows,url=download()
    matches={}
    identity={}
    unknown=0
    future_rows=0
    future_supported=0
    unmatched_future=[]
    for row in rows:
        t=kickoff(row)
        if t and NOW<t<=NOW+timedelta(days=8):
            future_rows+=1
            if CODES.get(str(row.get("Div") or "").strip()):future_supported+=1
        gid=fixture_for(row,games)
        if not gid:
            unknown+=1
            if t and NOW<t<=NOW+timedelta(days=8) and CODES.get(str(row.get("Div") or "").strip()):
                unmatched_future.append({"division":str(row.get("Div") or ""),"date":str(row.get("Date") or ""),
                   "time":str(row.get("Time") or ""),"home":str(row.get("HomeTeam") or ""),
                   "away":str(row.get("AwayTeam") or "")})
            continue
        quotes=decode(row)
        if quotes and gid not in matches:
            matches[gid]=quotes
            identity[gid]={"competition":row.get("Div"),
              "publishedHome":row.get("HomeTeam"),"publishedAway":row.get("AwayTeam"),
              "kickoffUtc":kickoff(row).isoformat()}
    output={
        "generatedAt":NOW.isoformat(),"source":"Football-Data.co.uk — free pre-match fixture CSV",
        "sourceUrl":url or URLS[0],"downloaded":bool(rows),"csvRows":len(rows),
        "unmatchedRows":unknown,"futureRows":future_rows,"futureSupportedRows":future_supported,
        "unmatchedFutureExamples":unmatched_future[:5],
        "matchedGames":len(matches),"matches":matches,
        "matchEvidence":identity,
        "note":"Internacional: odds recolhidas periodicamente pelo publisher, não ao vivo. Não inclui Betano Portugal e nunca confirma o boletim."
    }
    old=read(DEST)
    if old.get("matches")==matches and old.get("downloaded")==output["downloaded"] and old.get("csvRows")==len(rows) and old.get("futureRows")==future_rows and old.get("futureSupportedRows")==future_supported and old.get("unmatchedFutureExamples")==unmatched_future[:5]:
        print("Football-Data fixtures odds unchanged;",len(matches),"matches");return
    DEST.parent.mkdir(parents=True,exist_ok=True)
    DEST.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Football-Data pre-match odds:",len(rows),"rows,",future_rows,"future,",future_supported,"supported future,",len(matches),"verified games")
if __name__=="__main__":main()
