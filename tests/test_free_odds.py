import importlib.util
from pathlib import Path
from datetime import timedelta
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("sync_free_odds",ROOT/"scripts"/"sync_free_odds.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
calendar=[{"id":"espn-999","home":"FC Porto","away":"Braga",
 "leagueCode":"por.1","utc":(m.NOW+timedelta(days=1)).replace(microsecond=0).isoformat()}]
def example():
 return {"commence_time":calendar[0]["utc"],"home_team":"FC Porto","away_team":"Braga",
  "bookmakers":[
   {"title":"Betclic","last_update":(m.NOW-timedelta(minutes=12)).isoformat(),
    "markets":[{"key":"h2h","outcomes":[
      {"name":"FC Porto","price":1.8},{"name":"Braga","price":4.5},{"name":"Draw","price":3.7}]},
      {"key":"totals","outcomes":[{"name":"Over","point":2.5,"price":1.9},
                                   {"name":"Under","point":2.5,"price":1.95}]}]},
   {"title":"Betfair","last_update":(m.NOW-timedelta(minutes=5)).isoformat(),
    "markets":[{"key":"h2h","outcomes":[
      {"name":"FC Porto","price":1.84},{"name":"Braga","price":4.6},{"name":"Draw","price":3.8}]}]}
  ]}
class OddsProviderTests(unittest.TestCase):
 def test_real_match_no_vig_consensus_and_reference_only(self):
  gid,prices=m.parse_event(example(),calendar,"por.1")
  self.assertEqual(gid,"espn-999")
  self.assertAlmostEqual(prices["O25"]["odd"],1.9)
  self.assertEqual(prices["1X2_H"]["fairBooks"],2)
  self.assertIsNotNone(prices["1X2_H"]["fairMarketConsensus"])
  self.assertFalse(prices["1X2_H"]["betanoConfirmedOnSlip"])
  self.assertTrue(prices["1X2_H"]["verifiedTeams"])
 def test_market_does_not_create_false_btts_or_ht(self):
  _,prices=m.parse_event(example(),calendar,"por.1")
  self.assertNotIn("HT_H",prices)
  self.assertNotIn("BTTS_Y",prices)
 def test_other_competition_and_wrong_teams_rejected(self):
  self.assertIsNone(m.parse_event(example(),calendar,"esp.1"))
  e=example();e["away_team"]="Benfica"
  self.assertIsNone(m.parse_event(e,calendar,"por.1"))
 def test_stale_bookmaker_not_quoted(self):
  e=example()
  for x in e["bookmakers"]:x["last_update"]=(m.NOW-timedelta(days=4)).isoformat()
  self.assertIsNone(m.parse_event(e,calendar,"por.1"))
 def test_at_most_two_league_queries_per_cycle(self):
  self.assertLessEqual(len(m.next_sports(calendar)),2)
if __name__=="__main__":unittest.main()
