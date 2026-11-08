import importlib.util
import unittest
from pathlib import Path

spec=importlib.util.spec_from_file_location("sync_analysis",Path(__file__).resolve().parents[1]/"scripts"/"sync_analysis.py")
model=importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)

class AnalysisTests(unittest.TestCase):
    def test_name_matching(self):
        self.assertEqual(model.team_match("Manchester United",{"Man United","Man City"}),"Man United")
        self.assertEqual(model.team_match("Real Sociedad",{"Sociedad","Real Madrid"}),"Sociedad")
        self.assertIsNone(model.team_match("Unknown Football Club",{"Manchester United","Manchester City"}))
    def test_only_real_completed_results_count(self):
        rows=[
            {"Date":"01/10/2026","HomeTeam":"Alpha","AwayTeam":"Beta","FTHG":"2","FTAG":"1"},
            {"Date":"04/10/2026","HomeTeam":"Gamma","AwayTeam":"Alpha","FTHG":"0","FTAG":"1"},
            {"Date":"08/10/2026","HomeTeam":"Alpha","AwayTeam":"Delta","FTHG":"3","FTAG":"1"},
            {"Date":"11/10/2026","HomeTeam":"Beta","AwayTeam":"Alpha","FTHG":"1","FTAG":"1"},
            {"Date":"15/10/2026","HomeTeam":"Alpha","AwayTeam":"Gamma","FTHG":"2","FTAG":"0"},
            {"Date":"18/10/2026","HomeTeam":"Delta","AwayTeam":"Alpha","FTHG":"2","FTAG":"0"}
        ]
        rates=model.calculate_rates(model.form_for("Alpha",rows))
        self.assertEqual(rates["games"],6)
        self.assertEqual(rates["homeGames"],3)
        self.assertEqual(rates["awayGames"],3)
        self.assertAlmostEqual(rates["homeFor"],7/3)
    def test_poisson_preview_is_not_approved_bet(self):
        h={"games":10,"homeGames":5,"awayGames":5,"homeFor":1.8,"homeAgainst":1.0,"awayFor":1.3,"awayAgainst":1.4,"allFor":1.55,"allAgainst":1.2}
        a={"games":10,"homeGames":5,"awayGames":5,"homeFor":1.1,"homeAgainst":1.5,"awayFor":1.4,"awayAgainst":1.1,"allFor":1.25,"allAgainst":1.3}
        result=model.project(h,a,2)
        self.assertTrue(result["markets"])
        self.assertTrue(all(row["status"]=="OBSERVAR" for row in result["markets"]))
        outcomes=[x["probability"] for x in result["markets"] if x["key"].startswith("1X2_")]
        self.assertAlmostEqual(sum(outcomes),1.0,places=4)
        self.assertTrue(all(x["minimumOdd"] is None or x["minimumOdd"]>=1.01 for x in result["markets"]))
if __name__=="__main__":unittest.main()
