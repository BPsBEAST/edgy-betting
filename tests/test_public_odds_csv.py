import importlib.util
from pathlib import Path
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
spec=importlib.util.spec_from_file_location("sync_football_data_odds",ROOT/"scripts"/"sync_football_data_odds.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
KICK=(m.NOW+timedelta(days=1)).astimezone(ZoneInfo("Europe/London")).replace(second=0,microsecond=0)
CAL=[{"id":"espn-porto","home":"FC Porto","away":"Braga","leagueCode":"por.1",
      "utc":KICK.astimezone(timezone.utc).isoformat()}]
ROW={"Div":"P1","Date":KICK.strftime("%d/%m/%Y"),"Time":KICK.strftime("%H:%M"),
     "HomeTeam":"Porto","AwayTeam":"Braga",
     "B365H":"1.90","B365D":"3.40","B365A":"4.10",
     "BWH":"1.91","BWD":"3.45","BWA":"4.11",
     "PSH":"1.95","PSD":"3.40","PSA":"4.05",
     "B365>2.5":"1.87","B365<2.5":"1.95",
     "P>2.5":"1.88","P<2.5":"1.98"}
class PublicOddsCSVTests(unittest.TestCase):
 def test_match_strictly_by_clubs_division_and_time(self):
  self.assertEqual(m.fixture_for(ROW,CAL),"espn-porto")
  self.assertIsNone(m.fixture_for({**ROW,"AwayTeam":"Benfica"},CAL))
  self.assertIsNone(m.fixture_for({**ROW,"Div":"E0"},CAL))
  self.assertIsNone(m.fixture_for({**ROW,"Time":"05:00"},CAL))
 def test_missing_kickoff_is_not_guessed(self):
  self.assertIsNone(m.fixture_for({**ROW,"Time":""},CAL))
 def test_full_market_fair_odds_and_no_false_betano(self):
  prices=m.decode(ROW)
  self.assertEqual(prices["1X2_H"]["fairBooks"],3)
  self.assertEqual(prices["O25"]["fairBooks"],2)
  self.assertIsNotNone(prices["1X2_A"]["fairMarketConsensus"])
  self.assertEqual(prices["1X2_H"]["odd"],1.95)
  self.assertFalse(prices["1X2_H"]["betanoConfirmedOnSlip"])
  self.assertFalse(prices["1X2_H"]["betanoInFeed"])
 def test_one_outcome_does_not_get_fake_no_vig(self):
  self.assertNotIn("1X2_H",m.decode({"B365H":"1.9"}))
 def test_bogus_price_rejected(self):
  self.assertIsNone(m.number(float("nan")))
  self.assertIsNone(m.number(1.0))
  self.assertIsNone(m.number("free"))
if __name__=="__main__":unittest.main()
