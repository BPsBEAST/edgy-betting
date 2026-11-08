#!/usr/bin/env python3
"""Source-attributed current 1X2 market fair probabilities, no keys or payment.

TipsAudit explicitly provides its public API for reuse with visible attribution:
https://tipsaudit.com/api . Sharp bookmaker probabilities are not an
independent prediction-model vote and are not confirmed Betano prices.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError
from urllib.parse import urlparse
import sys

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/"data"/"market_fair.json"
FIXTURES=ROOT/"data"/"fixtures.json"
NOW=datetime.now(timezone.utc)
SOURCE="https://tipsaudit.com/api/v1/predictions"
sys.path.insert(0,str(ROOT/"scripts"))
import sync_free_predictions as matching
COMPETITIONS={
 "premier league":"Premier League",
 "england premier league":"Premier League",
 "english premier league":"Premier League",
 "championship":"Championship",
 "england championship":"Championship",
 "portugal primeira liga":"Primeira Liga",
 "primeira liga":"Primeira Liga",
 "liga portugal":"Primeira Liga",
 "italy serie a":"Serie A",
 "italian serie a":"Serie A",
 "serie a":"Serie A",
 "italy serie b":"Serie B",
 "serie b":"Serie B",
 "spain la liga":"La Liga",
 "la liga":"La Liga",
 "spain segunda division":"Segunda Division",
 "segunda division":"Segunda Division",
 "germany bundesliga":"Bundesliga",
 "bundesliga":"Bundesliga",
 "germany 2 bundesliga":"2 Bundesliga",
 "2 bundesliga":"2 Bundesliga",
 "france ligue 1":"Ligue 1",
 "ligue 1":"Ligue 1",
 "france ligue 2":"Ligue 2",
 "ligue 2":"Ligue 2",
 "uefa champions league":"UEFA Champions League",
 "champions league":"UEFA Champions League",
 "uefa europa league":"UEFA Europa League",
 "europa league":"UEFA Europa League",
 "uefa conference league":"UEFA Conference League"
}
def read(path):
    try:return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError,OSError):return {}
def is_fresh(ts,now=NOW,hours=5):
    when=matching.parse_time(ts)
    return bool(when and -300<=(now-when).total_seconds()<=hours*3600)
def normalize_league(raw):
    return COMPETITIONS.get(matching.norm(raw))
def decode(row,fixtures,now=NOW):
    if not isinstance(row,dict):return None
    league=normalize_league(row.get("league"))
    if not league:return None
    # Ignore logged fallback prices: only current sharp-market snapshots.
    if row.get("fair_source")!="live" or not is_fresh(row.get("fair_read_at"),now,5):return None
    p=matching.probabilities(row.get("fair_probabilities"))
    if not p:return None
    gid=matching.match({"competition":league,"kickoff":row.get("kickoff_utc"),
                        "home":row.get("home"),"away":row.get("away")},fixtures,now)
    if not gid:return None
    source_url=str(row.get("url") or "")
    if not (source_url.startswith("https://tipsaudit.com/") and len(source_url)<350):
        source_url="https://tipsaudit.com/api"
    quote=None
    value=row.get("value")
    if isinstance(value,dict) and row.get("status") in ("actionable","monitor") and is_fresh(row.get("fair_read_at"),now,1.5):
        selection=str(value.get("selection") or "").upper()
        key={"1":"1X2_H","X":"1X2_D","2":"1X2_A"}.get(selection)
        try:od=float(value.get("best_soft_odds"))
        except (TypeError,ValueError):od=0
        book=str(value.get("bookmaker") or "")[:70].strip()
        if key and book and 1.01<=od<=100:
            quote={"market":key,"odd":od,"bookmaker":book,
                   "source":"TipsAudit / soft-book market","referenceOnly":True,
                   "betanoConfirmedOnSlip":False}
    return gid,{"provider":"TipsAudit","sourceUrl":source_url,
       "fairProbability":p,"readAt":row.get("fair_read_at"),
       "fairSource":"Mercado sharp sem margem (não é previsão independente)",
       "quote":quote}
def get_data():
    try:
        req=Request(SOURCE,headers={"Accept":"application/json",
            "User-Agent":"EDGY-Betting/2.5 (TipsAudit free attribution API integration)"})
        with urlopen(req,timeout=15) as response:
            body=response.read(3_000_000)
        x=json.loads(body.decode("utf-8"))
        return x if isinstance(x,dict) else None
    except (URLError,OSError,ValueError) as exc:
        print("TipsAudit source unavailable:",str(exc)[:120]);return None
def main():
    records=read(FIXTURES).get("games") or []
    data=get_data()
    matches={}
    status="Fonte inacessível"
    if data and is_fresh(data.get("generated_at"),NOW,24):
        found=data.get("predictions") or []
        for row in found[:1200]:
            out=decode(row,records,NOW)
            if out:
                gid,payload=out
                matches.setdefault(gid,payload)
        status="Disponível" if matches else "Feed recente, sem correspondências seguras nas ligas e jogos selecionados"
    elif data:
        status="Feed devolvido, mas sem data recente verificável"
    result={
        "generatedAt":NOW.isoformat(),"provider":"TipsAudit (API pública gratuita, atribuição obrigatória)",
        "sourceUrl":"https://tipsaudit.com/api","status":status,
        "feedGeneratedAt":data.get("generated_at") if data else None,
        "matchedGames":len(matches),"matches":matches,
        "note":"Probabilidade justa do mercado sharp. Não conta como prognóstico Statarea/SportyTrader, não confirma Betano Portugal. URL de origem obrigatória."
    }
    old=read(DEST)
    if old.get("matches")==matches and old.get("status")==status:
        print("Market fair feed unchanged",len(matches));return
    DEST.parent.mkdir(parents=True,exist_ok=True)
    DEST.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("TipsAudit fair market",len(matches),"matches",status)
if __name__=="__main__":main()
