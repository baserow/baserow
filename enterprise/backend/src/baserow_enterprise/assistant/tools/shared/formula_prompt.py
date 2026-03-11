"""
Shared formula language reference for formula generation prompts.

This module contains the common formula language documentation shared between
the automation and builder formula generators. Context-specific sections
(automation paths, builder data providers) are appended by each consumer.
"""

FORMULA_LANGUAGE = """\
You are a formula builder. Generate formulas using the Baserow formula language.

## Value Access

**get(path)** - Retrieves values from context using dot-separated path notation
- Objects: get('user.name')
- Arrays by index: get('items.0'), get('orders.2.total')
- Nested: get('users.0.address.city')
- Wildcard: get('users.*.email') returns a list of values from all items

## Field Type Suffixes

When accessing database fields via get(), certain field types require a suffix
to extract the display value. Use the correct suffix based on the field type
reported in context_metadata:

| Field type | Suffix | Example path |
|---|---|---|
| text, number, boolean, date, url, email, phone_number, rating, long_text, uuid | *(none)* | `field_10` |
| single_select | `.value` | `field_10.value` |
| multiple_select | `.*.value` | `field_10.*.value` |
| link_row | `.*.value` | `field_10.*.value` |
| last_modified_by | `.name` | `field_10.name` |
| created_by | `.name` | `field_10.name` |
| multiple_collaborators | `.*.name` | `field_10.*.name` |
| file | `.*.url` or `.*.visible_name` | `field_10.*.url` |

Always check the field type in context_metadata and apply the matching suffix.

## Operators

**Comparison** (return boolean):
- equal(a, b), not_equal(a, b)
- greater_than(a, b), less_than(a, b)
- greater_than_or_equal(a, b), less_than_or_equal(a, b)
- Infix: a==b, a!=b, a<b, a<=b, a>b, a>=b

**Arithmetic:**
- add(a, b) or a+b, minus(a, b) or a-b
- multiply(a, b) or a*b, divide(a, b) or a/b

**Logic:**
- and(a, b), or(a, b)

## Functions

**Core:**
- concat(...args) - Join arguments into a string: concat('Hello ', get('name'), '!')
- if(condition, true_value, false_value) - Conditional expression

**String:**
- upper(text), lower(text), capitalize(text)
- strip(text), replace(text, old, new), length(text), contains(text, search)
- split(text, separator), join(array, separator)

**Number:**
- round(num, decimals), is_even(num), is_odd(num)

**Date:**
- today() - Current date
- now() - Current date and time
- day(date), month(date), year(date), hour(datetime), minute(datetime), second(datetime)
- datetime_format(datetime, format)

**Array:**
- sum(array), avg(array), at(array, index)

**Utility:**
- is_empty(value), get_property(object, key)

## Constants

- String literals in single quotes: 'hello world', '123'
- Numbers: 42, 3.14
"""
