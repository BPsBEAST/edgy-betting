import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("link_odds",ROOT/"scripts"/"link_odds.py")
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

API={"fixture":{"id":98123,"date":"2026-11-11T20:00:00+00:00"},"league":{"id":94},
 "teams":{"home":{"name":"FC Porto"},"away":{"name":"Casa Pia"}}}
CAL=[{"id":"espn-777","home":"Porto","away":"Casa Pia","leagueCode":"por.1","utc":"2026-11-11T20:00:00Z"}]

class SafeProviderMatching(unittest.TestCase):
 def test_exact_verified_match(self):
  self.assertEqual(module.match_fixture(API,CAL),"espn-777")
 def test_different_club_prevents_linking(self):
  wrong={"fixture":API["fixture"],"league":API["league"],"teams":{"home":{"name":"FC Porto"},"away":{"name":"Sporting Lisbon"}}}
  self.assertIsNone(module.match_fixture(wrong,CAL))
 def test_swapped_clubs_do_not_link(self):
  swapped={"fixture":API["fixture"],"league":API["league"],"teams":{"home":{"name":"Casa Pia"},"away":{"name":"FC Porto"}}}
  self.assertIsNone(module.match_fixture(swapped,CAL))
 def test_other_competition_does_not_link(self):
  wrong=dict(API,league={"id":39})
  self.assertIsNone(module.match_fixture(wrong,CAL))
 def test_kickoff_changed_by_hours_does_not_link(self):
  wrong=dict(API,fixture={"id":98123,"date":"2026-11-12T03:00:00Z"})
  self.assertIsNone(module.match_fixture(wrong,CAL))
 def test_ambiguous_duplicates_do_not_link(self):
  duplicated=[*CAL,dict(CAL[0],id="espn-888")]
  self.assertIsNone(module.match_fixture(API,duplicated))
 def test_alias_normalization(self):
  self.assertEqual(module.norm("Man Utd"),module.norm("Manchester United"))
  self.assertEqual(module.norm("Vitória de Guimarães"),module.norm("Vitória Guimarães"))
 def test_metadata_unique_kickoff_is_provisional_only(self):
  meta={"leagueId":94,"utc":"2026-11-11T20:00:00Z"}
  self.assertEqual(module.match_metadata(meta,CAL),"espn-777")
 def test_metadata_fails_on_ambiguous_simultaneous_match(self):
  meta={"leagueId":94,"utc":"2026-11-11T20:00:00Z"}
  self.assertIsNone(module.match_metadata(meta,CAL+[dict(CAL[0],id="espn-888")]))
 def test_metadata_fails_when_competition_differs(self):
  self.assertIsNone(module.match_metadata({"leagueId":39,"utc":"2026-11-11T20:00:00Z"},CAL))
 def test_metadata_fails_when_kickoff_differs(self):
  self.assertIsNone(module.match_metadata({"leagueId":94,"utc":"2026-11-11T20:25:00Z"},CAL))
 def test_metadata_fails_without_time(self):
  self.assertIsNone(module.match_metadata({"leagueId":94},CAL))
if __name__=="__main__":unittest.main()
