import importlib.util
from pathlib import Path
from datetime import datetime,timedelta,timezone
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("extra_markets",ROOT/"scripts"/"extra_markets.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def rows():
 out=[]
 for i in range(8):
  day=(m.NOW-timedelta(days=i+2)).strftime("%d/%m/%Y")
  out.append({"Date":day,"HomeTeam":"Alpha","AwayTeam":"Gamma",
   "HTHG":str(i%3),"HTAG":"0","HC":"5","AC":"4","HS":"13","AS":"8","HST":"6","AST":"3"})
  out.append({"Date":day,"HomeTeam":"Gamma","AwayTeam":"Beta",
   "HTHG":"0","HTAG":str(i%2),"HC":"4","AC":"5","HS":"8","AS":"12","HST":"3","AST":"5"})
 return out
def model():
 return {"lambdaHome":1.5,"lambdaAway":1.2,
  "home":{"homeGames":6,"awayGames":6},
  "away":{"homeGames":6,"awayGames":6},"markets":[]}
class ExtraHistoricalMarketTests(unittest.TestCase):
 def test_corners_shots_interval_and_joint_combo(self):
  obj=m.enrich(model(),"Alpha","Beta",rows(),1)
  groups={x["group"] for x in obj["markets"]}
  self.assertTrue({"Intervalo","Cantos","Remates","Combinadas"}.issubset(groups))
  ht=[x["probability"] for x in obj["markets"] if x["key"] in ("HT_H","HT_D","HT_A")]
  self.assertAlmostEqual(sum(ht),1.,places=4)
  self.assertTrue(all(x["status"]=="OBSERVAR" for x in obj["markets"]))
  self.assertTrue(all(x["minimumOdd"] is None or x["minimumOdd"]>=1.01 for x in obj["markets"]))
  self.assertEqual(obj["extraStats"]["C"]["samplePerVenue"],8)
 def test_missing_shots_are_not_zero(self):
  redacted=[{k:v for k,v in row.items() if k not in ("HC","AC","HS","AS","HST","AST")} for row in rows()]
  obj=m.enrich(model(),"Alpha","Beta",redacted,2)
  groups={x["group"] for x in obj["markets"]}
  self.assertNotIn("Cantos",groups)
  self.assertNotIn("Remates",groups)
  self.assertIn("Intervalo",groups)
 def test_second_division_increases_uncertainty(self):
  one=m.enrich(model(),"Alpha","Beta",rows(),1)
  two=m.enrich(model(),"Alpha","Beta",rows(),2)
  self.assertGreater(two["markets"][0]["uncertainty"],one["markets"][0]["uncertainty"])
 def test_bets_with_minute_data_unavailable(self):
  obj=m.enrich(model(),"Alpha","Beta",rows(),1)
  self.assertTrue(any("minuto" in text.lower() for text in obj["unmodelledMarkets"]))
if __name__=="__main__":unittest.main()
