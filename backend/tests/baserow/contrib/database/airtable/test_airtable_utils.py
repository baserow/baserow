import pytest

from baserow.contrib.database.airtable.utils import (
    extract_share_id_from_url,
    get_airtable_row_primary_value,
    quill_to_markdown,
)


def test_extract_share_id_from_url():
    with pytest.raises(ValueError):
        extract_share_id_from_url("test")

    assert (
        extract_share_id_from_url("https://airtable.com/shrxxxxxxxxxxxxxx")
        == "shrxxxxxxxxxxxxxx"
    )
    assert (
        extract_share_id_from_url("https://airtable.com/appxxxxxxxxxxxxxx")
        == "appxxxxxxxxxxxxxx"
    )
    assert (
        extract_share_id_from_url("https://airtable.com/shrXxmp0WmqsTkFWTzv")
        == "shrXxmp0WmqsTkFWTzv"
    )

    long_share_id = (
        "shr22aXe5Hj32sPJB/tblU0bav59SSEyOkU/"
        "viwyUDJYyQPYuFj1F?blocks=bipEYER8Qq7fLoPbr"
    )
    assert (
        extract_share_id_from_url(f"https://airtable.com/{long_share_id}")
        == long_share_id
    )


def test_get_airtable_row_primary_value_with_primary_field():
    airtable_table = {
        "name": "Test",
        "primaryColumnId": "fldG9y88Zw7q7u4Z7i4",
    }
    airtable_row = {
        "id": "id1",
        "cellValuesByColumnId": {"fldG9y88Zw7q7u4Z7i4": "name1"},
    }
    assert get_airtable_row_primary_value(airtable_table, airtable_row) == "name1"


def test_get_airtable_row_primary_value_without_primary_field():
    airtable_table = {
        "name": "Test",
        "primaryColumnId": "fldG9y88Zw7q7u4Z7i4",
    }
    airtable_row = {"id": "id1"}
    assert get_airtable_row_primary_value(airtable_table, airtable_row) == "id1"


def test_get_airtable_row_primary_value_without_primary_column_id_in_table():
    airtable_table = {
        "name": "Test",
        "primaryColumnId": "test",
    }
    airtable_row = {"id": "id1"}
    assert get_airtable_row_primary_value(airtable_table, airtable_row) == "id1"


def test_quill_to_markdown_airtable_example():
    markdown_value = quill_to_markdown(
        [
            {"insert": "He"},
            {"attributes": {"bold": True}, "insert": "adi"},
            {"insert": "ng 1"},
            {"attributes": {"header": 1}, "insert": "\n"},
            {"insert": "He"},
            {"attributes": {"link": "https://airtable.com"}, "insert": "a"},
            {
                "attributes": {"link": "https://airtable.com", "bold": True},
                "insert": "di",
            },
            {"attributes": {"bold": True}, "insert": "n"},
            {"insert": "g 2"},
            {"attributes": {"header": 2}, "insert": "\n"},
            {"insert": "Heading 3"},
            {"attributes": {"header": 3}, "insert": "\n"},
            {"insert": "\none"},
            {"attributes": {"list": "ordered"}, "insert": "\n"},
            {"insert": "two"},
            {"attributes": {"list": "ordered"}, "insert": "\n"},
            {"insert": "three"},
            {"attributes": {"list": "ordered"}, "insert": "\n"},
            {"insert": "Sub 1"},
            {"attributes": {"indent": 1, "list": "ordered"}, "insert": "\n"},
            {"insert": "Sub 2"},
            {"attributes": {"indent": 1, "list": "ordered"}, "insert": "\n"},
            {"insert": "\none"},
            {"attributes": {"list": "bullet"}, "insert": "\n"},
            {"insert": "two"},
            {"attributes": {"list": "bullet"}, "insert": "\n"},
            {"insert": "three"},
            {"attributes": {"list": "bullet"}, "insert": "\n"},
            {"insert": "Sub 1"},
            {"attributes": {"indent": 1, "list": "bullet"}, "insert": "\n"},
            {"insert": "Sub 2"},
            {"attributes": {"indent": 1, "list": "bullet"}, "insert": "\n"},
            {"insert": "\nCheck 1"},
            {"attributes": {"list": "unchecked"}, "insert": "\n"},
            {"insert": "Check 2"},
            {"attributes": {"list": "unchecked"}, "insert": "\n"},
            {"insert": "Check 3"},
            {"insert": "\n", "attributes": {"list": "unchecked"}},
            {"insert": "\nLorem "},
            {"insert": "ipsum", "attributes": {"bold": True}},
            {"insert": " dolor "},
            {"attributes": {"italic": True}, "insert": "sit"},
            {"insert": " amet, "},
            {"attributes": {"strike": True}, "insert": "consectetur"},
            {"insert": " adipiscing "},
            {"attributes": {"code": True}, "insert": "elit"},
            {"insert": ". "},
            {"attributes": {"link": "https://airtable.com"}, "insert": "Proin"},
            {"insert": " ut metus quam. Ut tempus at "},
            {
                "attributes": {"link": "https://airtable.com"},
                "insert": "https://airtable.com",
            },
            {
                "insert": " vel varius. Phasellus nec diam vitae urna mollis cursus. Donec mattis pellentesque nunc id dictum. Maecenas vel tortor quam. Vestibulum et enim ut mauris lacinia malesuada. Pellentesque euismod\niaculis felis, at posuere velit ullamcorper a. Aliquam eu ultricies neque, cursus accumsan metus. Etiam consectetur eu nisi id aliquet. "
            },
            {
                "insert": {
                    "mention": {
                        "userId": "usrGIN77VWdhm7LKk",
                        "mentionId": "menuy6d9AwkWbnNXx",
                    }
                }
            },
            {
                "insert": " gravida vestibulum egestas. Praesent pretium velit eu pretium ultrices. Nullam ut est non quam vulputate "
            },
            {"attributes": {"code": True}, "insert": "tempus nec vel augue"},
            {
                "insert": ". Aenean dui velit, ornare nec tincidunt eget, fermentum sed arcu. Suspendisse consequat bibendum molestie. Fusce at pulvinar enim.\n"
            },
            {
                "insert": {
                    "mention": {
                        "userId": "usrGIN77VWdhm7LKk",
                        "mentionId": "menflYNpEgIJljLuR",
                    }
                }
            },
            {"insert": "\nQuote, but not actually"},
            {"attributes": {"blockquote": True}, "insert": "\n"},
            {"insert": "on multiple lines"},
            {"attributes": {"blockquote": True}, "insert": "\n"},
            {"insert": "\ncode"},
            {"attributes": {"code-block": True}, "insert": "\n"},
            {"insert": "line"},
            {"attributes": {"code-block": True}, "insert": "\n"},
            {"insert": "2"},
            {"insert": "\n", "attributes": {"code-block": True}},
            {"insert": "\n{"},
            {"insert": "\n", "attributes": {"code-block": True}},
            {"insert": '  "test": "test",'},
            {"attributes": {"code-block": True}, "insert": "\n"},
            {"insert": '  "yeah": "test"'},
            {"attributes": {"code-block": True}, "insert": "\n"},
            {"insert": "}"},
            {"insert": "\n", "attributes": {"code-block": True}},
        ]
    )
    assert (
        markdown_value
        == """# He**adi**ng 1
## He[a](https://airtable.com)[**di**](https://airtable.com)**n**g 2
### Heading 3

1. one
1. two
1. three
    1. Sub 1
    1. Sub 2

- one
- two
- three
    - Sub 1
    - Sub 2

- [ ] Check 1
- [ ] Check 2
- [ ] Check 3

Lorem **ipsum** dolor _sit_ amet, ~consectetur~ adipiscing `elit`. [Proin](https://airtable.com) ut metus quam. Ut tempus at [https://airtable.com](https://airtable.com) vel varius. Phasellus nec diam vitae urna mollis cursus. Donec mattis pellentesque nunc id dictum. Maecenas vel tortor quam. Vestibulum et enim ut mauris lacinia malesuada. Pellentesque euismod
iaculis felis, at posuere velit ullamcorper a. Aliquam eu ultricies neque, cursus accumsan metus. Etiam consectetur eu nisi id aliquet. @usrGIN77VWdhm7LKk gravida vestibulum egestas. Praesent pretium velit eu pretium ultrices. Nullam ut est non quam vulputate `tempus nec vel augue`. Aenean dui velit, ornare nec tincidunt eget, fermentum sed arcu. Suspendisse consequat bibendum molestie. Fusce at pulvinar enim.
@usrGIN77VWdhm7LKk
> Quote, but not actually
> on multiple lines

```
code
line
2
```

```
{
  "test": "test",
  "yeah": "test"
}
```"""
    )


def test_quill_to_markdown_airtable_example_two_lists():
    markdown_value = quill_to_markdown(
        [
            {"insert": "This is great"},
            {"insert": "\n", "attributes": {"header": 2}},
            {"insert": "option 1"},
            {"attributes": {"list": "unchecked"}, "insert": "\n"},
            {"insert": "option 2"},
            {"attributes": {"list": "unchecked"}, "insert": "\n"},
            {"insert": "option that is "},
            {"attributes": {"bold": True}, "insert": "bold"},
            {"attributes": {"list": "unchecked"}, "insert": "\n"},
            {"insert": "\n"},
            {"attributes": {"bold": True}, "insert": "item"},
            {"attributes": {"list": "bullet"}, "insert": "\n"},
            {"attributes": {"italic": True}, "insert": "item"},
            {"attributes": {"list": "bullet"}, "insert": "\n"},
            {"attributes": {"strike": True}, "insert": "Item"},
            {"attributes": {"list": "bullet"}, "insert": "\n"},
            {"attributes": {"link": "https://airtable.com"}, "insert": "link"},
            {"insert": "\n", "attributes": {"list": "bullet"}},
        ]
    )
    assert (
        markdown_value
        == """## This is great
- [ ] option 1
- [ ] option 2
- [ ] option that is **bold**

- **item**
- _item_
- ~Item~
- [link](https://airtable.com)"""
    )
