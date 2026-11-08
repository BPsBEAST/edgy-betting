import importlib.util
from datetime import timedelta
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("sync_espn_context",ROOT/"scripts"/"sync_espn_context.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
GAME={"id":"espn-123456789","home":"Porto","away":"Braga","homeId":"11","awayId":"22",
 "leagueCode":"por.1","utc":(m.NOW+timedelta(minutes=35)).isoformat()}
def payload(count=11):
 def entries(tid):return {"team":{"id":tid},"roster":[{"starter":True,"athlete":{"displayName":f"Atleta {tid} #{i}"}} for i in range(count)]}
 return {"rosters":[entries("11"),entries("22")]}
class ESPNContextTests(unittest.TestCase):
 def test_exactly_two_sets_of_11_needed(self):
  lineups=m.read_lineups(payload(),GAME)
  self.assertTrue(lineups["confirmed"])
  self.assertEqual(len(lineups["teams"]),2)
  self.assertEqual(len(lineups["teams"][0]["startingXI"]),11)
 def test_partial_lineup_never_confirmed(self):
  self.assertIsNone(m.read_lineups(payload(10),GAME))
 def test_wrong_clubs_never_confirmed(self):
  o=payload()
  o["rosters"][0]["team"]["id"]="999"
  self.assertIsNone(m.read_lineups(o,GAME))
 def test_early_squad_does_not_confirm_starting_xi(self):
  self.assertIsNone(m.read_lineups(payload(),{**GAME,"utc":(m.NOW+timedelta(days=3)).isoformat()}))
 def test_injury_status_string_or_object(self):
  a=m.extract_team_injuries({"injuries":[{"athlete":{"displayName":"Foo"},"status":"Out"}]},{"name":"Porto"})
  b=m.extract_team_injuries({"injuries":[{"athlete":{"displayName":"Foo"},"status":{"type":"Questionable"}}]},{"name":"Porto"})
  self.assertEqual(a[0]["status"],"Out")
  self.assertEqual(b[0]["status"],"Questionable")
 def test_empty_response_does_not_mean_fully_fit(self):
  self.assertIsNone(m.extract_team_injuries({},{"name":"Porto"}))
if __name__=="__main__":unittest.main()
