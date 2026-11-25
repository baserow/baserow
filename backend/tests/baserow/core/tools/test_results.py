from baserow.core.tools.results import fit_result, fit_values, json_length


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


def test_fit_result_leaves_a_result_that_fits_as_it_is():
    result = {"results": [{"id": 1}], "has_next_page": False}

    assert fit_result(result, 1000) is result


def test_fit_result_keeps_the_first_items_whole_and_leaves_the_others_out():
    rows = [{"id": index, "name": "x" * 50} for index in range(10)]
    result = {"results": rows, "has_next_page": False}

    fitted = fit_result(result, 300)

    assert fitted["results"] == rows[: len(fitted["results"])]
    assert 0 < len(fitted["results"]) < 10
    assert fitted["truncated"] is True
    assert fitted["has_next_page"] is False
    assert json_length(fitted) <= 300


def test_fit_result_cuts_the_first_item_when_not_even_it_fits():
    result = {"results": [{"id": 1, "body": "x" * 500}]}

    fitted = fit_result(result, 200)

    assert fitted["results"][0]["id"] == 1
    assert fitted["results"][0]["body"].endswith("…")
    assert json_length(fitted) <= 200


def test_fit_result_cuts_the_values_of_another_object_and_any_other_value():
    assert fit_result({"result": "x" * 500}, 100)["truncated"] is True
    assert fit_result("x" * 500, 100) == "x" * 99 + "…"
