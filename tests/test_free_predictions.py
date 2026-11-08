import importlib.util
from pathlib import Path
from datetime import datetime, timezone, timedelta
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("sync_free_predictions",ROOT/"scripts"/"sync_free_predictions.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
NOW=datetime(2026,11,8,19,tzinfo=timezone.utc)
CAL=[{"id":"espn-111","home":"Tottenham Hotspur","away":"Chelsea",
      "leagueCode":"eng.1","utc":"2026-11-09T20:00:00Z"},
     {"id":"espn-222","home":"FC Porto","away":"Braga",
      "leagueCode":"por.1","utc":"2026-11-10T20:00:00Z"}]
def stamp(x):return x.isoformat().replace("+00:00","Z")
class FreePredictionTests(unittest.TestCase):
 def test_probability_missing_is_not_zero(self):
  self.assertIsNone(m.probabilities({"home":.55,"draw":.25}))
  self.assertIsNone(m.probabilities({"home":.55,"draw":.25,"away":.55}))
  self.assertEqual(m.probabilities({"home":.5,"draw":.3,"away":.2})["1X2_H"],.5)
 def test_exact_teams_kickoff_and_alias_match(self):
  row={"competition":"Premier League","kickoff":"2026-11-09T20:00:00Z",
       "home":"Spurs","away":"Chelsea"}
  self.assertEqual(m.match(row,CAL,NOW),"espn-111")
 def test_swapped_teams_do_not_match(self):
  row={"competition":"Premier League","kickoff":"2026-11-09T20:00:00Z",
       "home":"Chelsea","away":"Spurs"}
  self.assertIsNone(m.match(row,CAL,NOW))
 def test_wrong_competition_and_kickoff_do_not_match(self):
  row={"competition":"Bundesliga","kickoff":"2026-11-09T20:00:00Z","home":"Spurs","away":"Chelsea"}
  self.assertIsNone(m.match(row,CAL,NOW))
  row["competition"]="Premier League"
  row["kickoff"]="2026-11-09T22:00:00Z"
  self.assertIsNone(m.match(row,CAL,NOW))
 def test_ambiguity_does_not_match(self):
  row={"competition":"Premier League","kickoff":"2026-11-09T20:00:00Z","home":"Spurs","away":"Chelsea"}
  self.assertIsNone(m.match(row,CAL+[dict(CAL[0],id="espn-copy")],NOW))
 def test_staleness(self):
  self.assertFalse(m.fresh(stamp(NOW-timedelta(days=4)),NOW))
  self.assertTrue(m.fresh(stamp(NOW-timedelta(hours=3)),NOW))
 def test_stale_kqiq_feed_rejected_even_if_fixture_future(self):
  data={"generated_at":stamp(NOW-timedelta(days=4)),"fixtures":[
    {"competition":"Premier League","kickoff_iso":"2026-11-09T20:00:00Z",
     "home":"Spurs","away":"Chelsea","home_win_prob":.5,"draw_prob":.3,"away_win_prob":.2}]}
  matched,status=m.sources_from_kiqiq(data,CAL,NOW)
  self.assertEqual(matched,{})
  self.assertIn("atualizado",status)
 def test_kiqiq_valid_payload(self):
  data={"generated_at":stamp(NOW-timedelta(minutes=30)),"fixtures":[
    {"competition":"Premier League","kickoff_iso":"2026-11-09T20:00:00Z",
     "home":"Spurs","away":"Chelsea","home_win_prob":.5,"draw_prob":.3,"away_win_prob":.2}]}
  matched,_=m.sources_from_kiqiq(data,CAL,NOW)
  self.assertEqual(matched["espn-111"]["probabilities"]["1X2_D"],.3)
 def test_skorbot_only_upcoming_and_updated(self):
  data={"generated_at":stamp(NOW),"matches":[
   {"competition":"Premier League","kickoff":"2026-11-09T20:00:00Z",
    "home":"Spurs","away":"Chelsea","status":"scheduled",
    "updated_at":stamp(NOW-timedelta(minutes=2)),
    "probabilities":{"home":.55,"draw":.24,"away":.21}},
   {"competition":"Primeira Liga","kickoff":"2026-11-10T20:00:00Z",
    "home":"Porto","away":"Braga","status":"finished",
    "updated_at":stamp(NOW),"probabilities":{"home":.55,"draw":.24,"away":.21}}]}
  matched,_=m.sources_from_skorbot(data,CAL,NOW)
  self.assertEqual(list(matched),["espn-111"])
  self.assertEqual(matched["espn-111"]["provider"],"Skorbot")
if __name__=="__main__":unittest.main()
