from baserow.core.tools.results import fit_values, json_length


def skeleton_length(values):
    return json_length(dict.fromkeys(values, ""))


def test_json_length_counts_characters_as_read():
    assert json_length({"name": "é"}) == len('{"name": "é"}')


def test_fit_values_keeps_first_values_whole_and_marks_the_cut():
    values = {"title": "Refunds", "body": "x" * 100, "notes": "more"}
    max_length = skeleton_length(values) + 50

    fitted = fit_values(values, max_length)

    assert fitted["title"] == "Refunds"
    assert fitted["body"] == "x" * (50 - len("Refunds") - 1) + "…"
    assert fitted["notes"] == ""
    assert json_length(fitted) <= max_length
    assert values["body"] == "x" * 100


def test_fit_values_cuts_a_value_that_isnt_text_and_keeps_what_fits_after_it():
    values = {"id": 1, "files": [{"url": "x" * 100}] * 10, "notes": "Refunds"}
    expected = {"id": 1, "files": "…", "notes": "Refunds"}

    assert fit_values(values, json_length(expected)) == expected


def test_fit_values_leaves_fitting_values_alone():
    values = {"id": 1, "title": "Refunds"}

    assert fit_values(values, json_length(values)) == values


def test_fit_values_gives_up_when_even_the_keys_dont_fit():
    values = {"title": "Refunds", "body": "Text"}

    assert fit_values(values, skeleton_length(values) - 1) is None
