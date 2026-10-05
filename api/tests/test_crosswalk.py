import pytest
from build_crosswalk import build, load_overrides, match_one, normalise

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


def test_base_name_is_last_resort_and_approximate():
    names = ["Caulfield", "Box Hill", "Brighton", "Brighton East", "Croydon-Lilydale"]
    assert match_one("CAULFIELD NORTH", names) == ("matched", ["Caulfield"], "base_name")
    assert match_one("BOX HILL SOUTH", names)[2] == "base_name"
    assert match_one("CROYDON NORTH", names) == ("matched", ["Croydon-Lilydale"], "base_name")
    assert match_one("BRIGHTON EAST", names) == ("matched", ["Brighton East"], "exact")  # exact beats base name
    assert match_one("UPPER FERNTREE GULLY", ["Ferntree Gully"])[2] == "base_name"
    assert match_one("KEILOR DOWNS", ["Keilor"])[0] == "unmatched"  # "Downs" is not a qualifier
    cw = build(["CAULFIELD NORTH", "BRIGHTON"], names)
    assert cw["listing_to_arima"]["CAULFIELD NORTH"]["approximate"] is True
    assert cw["listing_to_arima"]["BRIGHTON"]["approximate"] is False
    assert cw["stats"]["approximate"] == 1


def test_component_word_order():
    assert match_one("ST KILDA WEST", ARIMA) == ("matched", ["Albert Park-Middle Park-West St Kilda"], "component_word_order")


def test_overrides(tmp_path):
    f = tmp_path / "o.csv"
    f.write_text("# comment\nlisting_suburb,arima_suburb,note\nmelbourne,Brighton,test\n")
    ov = load_overrides(f, ARIMA)
    cw = build(["MELBOURNE"], ARIMA, ov)
    assert cw["listing_to_arima"]["MELBOURNE"] == {"arima": "Brighton", "rule": "override", "approximate": True}
    f.write_text("listing_suburb,arima_suburb,note\nMELBOURNE,Nowhere,bad\n")
    with pytest.raises(ValueError):
        load_overrides(f, ARIMA)
