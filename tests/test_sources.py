import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/(name+".py"))
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
odds=module("sync_odds")
context=module("sync_context")

class MarketSourceTests(unittest.TestCase):
    def test_exact_markets(self):
        cases=[
          ("Match Winner","Home","1X2_H"),
          ("Match Winner","Draw","1X2_D"),
          ("Over/Under 2.5","Over","O25"),
          ("Over/Under 2.5","Under","U25"),
          ("Goals Over/Under","Over 1.5","O15"),
          ("Both Teams Score","Yes","BTTS_Y"),
          ("First Half Winner","Away","HT_A"),
          ("Correct Score","2:1","CS_2_1"),
          ("Draw No Bet","Home","DNB_H")]
        for bet,value,expected in cases:
            with self.subTest(bet=bet,value=value):
                self.assertEqual(odds.key_for(bet,value),expected)
    def test_no_vig_requires_complete_bookmaker_market(self):
        raw={"bookmakers":[
         {"name":"Betano","bets":[{"name":"Match Winner","values":[{"value":"Home","odd":"2.15"},{"value":"Draw","odd":"3.4"},{"value":"Away","odd":"3.2"}]}]},
         {"name":"Other","bets":[{"name":"Match Winner","values":[{"value":"Home","odd":"2.2"},{"value":"Draw","odd":"3.25"},{"value":"Away","odd":"3.15"}]}]}
         ]}
        out=odds.decode_event(raw)
        self.assertEqual(out["1X2_H"]["bookmaker"],"Betano")
        self.assertIsNotNone(out["1X2_H"]["fairMarketConsensus"])
        self.assertEqual(out["1X2_H"]["fairBooks"],2)
        self.assertFalse(out["1X2_H"]["betanoConfirmedOnSlip"])
    def test_weather_is_city_level_only_and_uses_real_hour(self):
        actual=context.get
        try:
            context.get=lambda *a,**k:{"hourly":{
              "time":["2026-11-09T18:00"],
              "precipitation":[8.5],"wind_gusts_10m":[53],"temperature_2m":[13]}}
            from datetime import datetime,timezone
            v=context.weather_forecast(41.1,-8.6,datetime(2026,11,9,18,tzinfo=timezone.utc))
            self.assertTrue(v["alert"])
            self.assertIn("cidade",v["scope"])
        finally:context.get=actual
    def test_venue_unknown_has_no_invented_geocode(self):
        self.assertEqual(context.country({"league":"Portugal · Primeira Liga"}),"PT")
        self.assertIsNone(context.country({"league":"UEFA · Champions League"}))

if __name__=="__main__":unittest.main()
