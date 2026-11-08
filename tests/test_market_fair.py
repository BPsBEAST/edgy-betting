import importlib.util
from pathlib import Path
from datetime import datetime,timedelta,timezone
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
spec=importlib.util.spec_from_file_location("sync_market_fair",ROOT/"scripts"/"sync_market_fair.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
NOW=m.NOW
CAL=[{"id":"espn-porto","leagueCode":"por.1","home":"FC Porto","away":"Braga",
 "utc":(NOW+timedelta(days=1)).isoformat()}]
def row():
 return {"league":"Portugal Primeira Liga","home":"Porto","away":"Braga",
 "kickoff_utc":CAL[0]["utc"],"fair_source":"live",
 "fair_read_at":(NOW-timedelta(minutes=10)).isoformat(),
 "fair_probabilities":{"home":.55,"draw":.25,"away":.2},
 "status":"actionable",
 "value":{"selection":"1","best_soft_odds":1.94,"bookmaker":"Unibet NL"},
 "url":"https://tipsaudit.com/match/123/porto-braga"}
class PublicFairMarketTests(unittest.TestCase):
 def test_recent_fair_probabilities_are_attributed(self):
  gid,out=m.decode(row(),CAL)
  self.assertEqual(gid,"espn-porto")
  self.assertEqual(out["fairProbability"]["1X2_H"],.55)
  self.assertEqual(out["quote"]["bookmaker"],"Unibet NL")
  self.assertFalse(out["quote"]["betanoConfirmedOnSlip"])
 def test_missing_or_stale_market_not_used(self):
  bad=row();bad["fair_source"]="logged"
  self.assertIsNone(m.decode(bad,CAL))
  bad=row();bad["fair_read_at"]=(NOW-timedelta(days=1)).isoformat()
  self.assertIsNone(m.decode(bad,CAL))
 def test_wrong_team_does_not_get_linked(self):
  bad=row();bad["away"]="Benfica"
  self.assertIsNone(m.decode(bad,CAL))
 def test_non_tipsaudit_link_is_blocked(self):
  bad=row();bad["url"]="https://phishing.test/"
  result=m.decode(bad,CAL)
  self.assertEqual(result[1]["sourceUrl"],"https://tipsaudit.com/api")
 def test_old_soft_quote_not_present_but_fair_usable(self):
  bad=row();bad["fair_read_at"]=(NOW-timedelta(hours=2)).isoformat()
  result=m.decode(bad,CAL)
  self.assertIsNotNone(result)
  self.assertIsNone(result[1]["quote"])
if __name__=="__main__":unittest.main()
