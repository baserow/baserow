from baserow.core.tools.results import fit_text_values, json_length


def test_json_length_counts_characters_as_read():
    assert json_length({"name": "é"}) == len('{"name": "é"}')


def test_fit_text_values_keeps_first_values_whole_and_marks_the_cut():
    values = {"id": 1, "title": "Refunds", "body": "x" * 100, "notes": "more"}
    max_length = json_length({**values, "title": "", "body": "", "notes": ""}) + 50

    fitted = fit_text_values(values, max_length)

    assert fitted["id"] == 1
    assert fitted["title"] == "Refunds"
    assert fitted["body"] == "x" * (50 - len("Refunds") - 1) + "…"
    assert fitted["notes"] == ""
    assert json_length(fitted) <= max_length
    assert values["body"] == "x" * 100


def test_fit_text_values_leaves_fitting_values_alone():
    values = {"id": 1, "title": "Refunds"}

    assert fit_text_values(values, json_length(values)) == values


def test_fit_text_values_gives_up_when_the_other_values_dont_fit():
    values = {"ids": list(range(100)), "title": "Refunds"}

    assert fit_text_values(values, 20) is None
