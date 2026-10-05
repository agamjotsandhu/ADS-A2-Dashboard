from build_crosswalk import build, match_one, normalise

ARIMA = ["Albert Park-Middle Park-West St Kilda", "South Kingsville-Altona North", "North Bendigo",
         "Mount Waverley", "Brighton", "Brighton East", "St Kilda", "Kew-Kew East", "Kew East-Balwyn"]


def test_normalise():
    assert normalise("Mt Waverley (Vic.)") == "mount waverley"
    assert normalise("ST KILDA") == "saint kilda"
    assert normalise("Albert Park") == normalise("ALBERT  PARK")


def test_rules():
    assert match_one("BRIGHTON", ARIMA)[:2] == ("matched", ["Brighton"])
    assert match_one("MT WAVERLEY", ARIMA)[2] == "exact"
    assert match_one("BENDIGO NORTH", ARIMA) == ("matched", ["North Bendigo"], "word_order")
    assert match_one("MIDDLE PARK", ARIMA) == ("matched", ["Albert Park-Middle Park-West St Kilda"], "component")
    assert match_one("ST KILDA", ARIMA)[:2] == ("matched", ["St Kilda"])  # exact beats component
    status, cands, _ = match_one("KEW EAST", ARIMA)
    assert status == "ambiguous" and len(cands) == 2
    assert match_one("BRIGHTEN EAST", ARIMA)[0] == "matched"  # fuzzy typo
    assert match_one("TOORAK", ARIMA)[0] == "unmatched"


def test_build_stats_and_reverse_map():
    cw = build(["BRIGHTON", "MIDDLE PARK", "ALBERT PARK", "KEW EAST", "TOORAK"], ARIMA)
    s = cw["stats"]
    assert (s["matched"], s["ambiguous"], s["unmatched"]) == (3, 1, 1)
    assert cw["arima_to_listing"]["Albert Park-Middle Park-West St Kilda"] == ["ALBERT PARK", "MIDDLE PARK"]
    assert {r["listing_suburb"] for r in cw["_review"]} == {"KEW EAST", "TOORAK"}


def test_no_arima_data_means_all_unmatched():
    cw = build(["BRIGHTON"], [])
    assert cw["stats"]["unmatched"] == 1 and cw["listing_to_arima"] == {}
