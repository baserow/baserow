# Baserow Documentation

Source: https://baserow.io/user-docs/understanding-formulas

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Formula field reference

Use formula fields effectively by performing calculations, manipulating text, using conditional statements, and exploring additional functions in Baserow’s formula field reference.

In this section, we will cover the concepts related to formulas. If you want a field to present its own value, a formula field can be useful. A formula can be used to calculate a field value based on other table values.

## Overview

The formula field type supports the [duration field type](/user-docs/duration-field). This means you can use a duration field to do simple mathematical operations, like adding and subtracting, directly.

Baserow’s formula field type supports [multiple select fields](/user-docs/multiple-select-field). Using a formula with a multiple select field allows you to display which fields include specific options and perform further manipulations with this data.

See the [understanding baserow formulas guide](/docs/tutorials/understanding-baserow-formulas) if you instead want a general guide of how to use formulas as a user within Baserow.

![Multiple select support in the formula field type](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/dd98fe74-d278-4708-b303-11420060fe5c/Multiple%20select%20support%20in%20the%20formula%20field%20type.png)   

## URL functions

Functions | Details | Syntax | Examples  
---|---|---|---  
button | Creates a button using the URI (first argument) and label (second argument). | button(text, text) | button(‘<http://your-text-here.com>’, ‘your-label’)  
get link label | Gets the label from a formula using the link or button functions. | get_link_label(button) | get_link_label(field(‘formula button field’)) = ‘your-label’  
get link url | Gets the url from a formula using the link or button functions. | get_link_url(link) | get_link_url(field(‘formula link field’)) = ‘<http://your-text-here.com>’  
link | Creates a hyperlink using the URI provided in the first argument. | link(text) | link(‘<http://your-text-here.com>’)  
  
|  |  |   
  
### Create strong calls-to-action with buttons

Baserow formulas allow you to add buttons to your rows. When you click on one of these buttons, it opens a specific link. The link is determined by the values stored in the associated row.

![Formula buttons in Baserow](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/81b52ee9-8b60-4bab-a546-f9241f641d60/Untitled.png)   

## Formula functions

Functions | Details | Syntax | Examples  
---|---|---|---  
variance sample | Calculates the sample variance of the values and returns the result. The sample variance should be used when the provided values are only for a sample or subset of values for an underlying population. | variance_sample(numbers from lookup() or field()) | variance_sample(lookup(“link field”, “number field”)) variance_sample(field(“lookup field”)) variance_sample(field(“link field with number primary field”))  
variance pop | Calculates the population variance of the values and returns the result. The population variance should be used when the provided values contain a value for every single piece of data in the population. | variance_pop(numbers from lookup() or field()) | variance_pop(lookup(“link field”, “number field”)) variance_pop(field(“lookup field”)) variance_pop(field(“link field with number primary field”))  
sum | Sums all of the values and returns the result. | sum(numbers from lookup() or field()) | sum(lookup(“link field”, “number field”)) sum(field(“lookup field”)) sum(field(“link field with number primary field”))  
stddev sample | Calculates the sample standard deviation of the values and returns the result. The sample deviation should be used when the provided values are only for a sample or subset of values for an underlying population. | stddev_sample(numbers from lookup() or field()) | stddev_sample(lookup(“link field”, “number field”)) stddev_sample(field(“lookup field”)) stddev_sample(field(“link field with number primary field”))  
stddev pop | Calculates the population standard deviation of the values and returns the result. The population standard deviation should be used when the provided values contain a value for every single piece of data in the population. | stddev_pop(numbers from lookup() or field()) | stddev_pop(lookup(“link field”, “number field”)) stddev_pop(field(“lookup field”)) stddev_pop(field(“link field with number primary field”))  
min | Returns the smallest number from all the looked up values provided. | min(numbers from a lookup() or field()) | min(lookup(“link field”, “number field”)) min(field(“lookup field”)) min(field(“link field with text primary field”))  
max | Returns the largest number from all the looked up values provided. | max(numbers from a lookup() or field()) | max(lookup(“link field”, “number field”)) max(field(“lookup field”)) max(field(“link field with text primary field”))  
join | Concats all of the values from the first input together using the values from the second input. | join(text from lookup() or field(), text) | join(lookup(“link field”, “number field”), “_”) join(field(“lookup field”), field(“different lookup field”)) join(field(“link field with text primary field”), “,”)  
filter | Filters down an expression involving a lookup/link field reference or a lookup function call. | filter(an expression involving lookup() or field(a link/lookup field), boolean) | sum(filter(lookup(“link field”, “number field”), lookup(“link field”, “number field”) > 10)) filter(field(“lookup field”), contains(field(“lookup field”), “a”)) filter(field(“link field”) + “a”, length(field(“link field”)) > 10")  
every | Returns true if every one of the provided looked up values is true, false otherwise. | every(boolean values from a lookup() or field()) | every(field(“my lookup”) = “test”)  
count | Returns the number of items in its first argument. | count(array) | count(field(‘my link row field’))  
avg | Averages all of the values and returns the result. | avg(numbers from lookup() or field()) | avg(lookup(“link field”, “number field”)) avg(field(“lookup field”)) avg(field(“link field with number primary field”))  
any | Returns true if any one of the provided looked up values is true, false if they are all false. | any(boolean values from a lookup() or field()) | any(field(“my lookup”) = “test”)  
  
Functions | Details | Syntax | Examples  
---|---|---|---  
when empty | If the first input is calculated to be empty the second input will be returned instead, otherwise if the first input is not empty the first will be returned. | when_empty(any, same type as the first) | when_empty(field(“a”), “default”)  
row id | Returns the rows unique identifying number. | row_id() | concat("Row ", row_id())  
minus `-` | Returns its two arguments subtracted. | number - number minus(number, number) date - date date - date_interval date_interval - date_interval | 3-1 = 2  
lookup | Looks up the values from a field in another table for rows in a link row field. The first argument should be the name of a link row field in the current table and the second should be the name of a field in the linked table. | lookup(‘a link row field name’, ‘field name in other the table’) | lookup(‘link row field’, ‘first name’) = lookup(‘link row field’, ‘last name’)  
field | Returns the field named by the single text argument. | field(‘a field name’) | field(‘my text field’) = ‘flag’  
add `+` | Returns its two arguments added together. | number + number text + text date + date_interval date_interval + date_interval date_interval + date add(number, number) | 1+1 = 2 ‘a’ + ‘b’ = ‘ab’  
date interval | Returns the date interval corresponding to the provided argument. | date_interval(text) | date_interval(‘1 year’) date_interval(‘2 seconds’)  
  
|  |  |   
  
## Date and time functions

Build more powerful formulas around dates in Baserow. The `today()` and `now()` functions update every 10 minutes.

The `today()` function is useful for calculating intervals or when you need to have the current date displayed on a table. The `now()` function is useful when you need to display the current date and time on your table or calculate a value based on the current date and time, and have that value updated each time you open your database.

> You can check if a date field is a specific day of the week in Baserow using a formula. [Learn more here](/user-docs/understanding-formulas#is-it-possible-to-check-if-a-date-is-a-specific-day-of-the-week).

Functions | Details | Syntax | Examples  
---|---|---|---  
year | Returns the number of years in the provided date. | year(date) | year(field(“my date”))  
now | Returns the current date and time in utc. | now() | now() > todate(“2021-12-12 13:00:00”, “YYYY-MM-DD HH24:MI:SS”)  
todate | Returns the first argument converted into a date given a date format string as the second argument. | todate(text, text) | todate(‘20210101’, ‘YYYYMMDD’)  
todate tz | Returns the first argument converted into a date given a date format string as the second argument and the [timezone](/user-docs/working-with-timezones) provided as third argument. | todate_tz(text, text, text) | now() > todate(“2021-12-12 13:00:00”, “YYYY-MM-DD HH24:MI:SS”)  
second | Returns the number of seconds in the provided date. | second(date) | second(field(“dates”)) == 2  
month | Returns the number of months in the provided date. | month(date) | month(todate(“2021-12-12”, “YYYY-MM-DD”)) = 12  
today | Returns the current date in utc. | today() | today() > todate(“2021-12-12”, “YYYY-MM-DD”)  
day | Returns the day of the month as a number between 1 to 31 from the argument. | day(date) | day(todate(‘20210101’, ‘YYYYMMDD’)) = 1  
datetime format | Converts the date to text given a way of formatting the date. | datetime_format(date, text) | datetime_format(field(‘date field’), ‘YYYY’)  
date diff | Given a date unit to measure in as the first argument (‘year’, ‘month’, ‘week’, ‘day’, ‘hour’, ‘minute’, ‘seconds’) calculates and returns the number of units from the second argument to the third. | date_diff(text, date, date) | date_diff(‘yy’, todate(‘2000-01-01’, ‘YYYY-MM-DD’), todate(‘2020-01-01’, ‘YYYY-MM-DD’)) = 20  
  
|  |  |   
  
## Boolean functions

Functions | Details | Syntax | Examples  
---|---|---|---  
or | Returns the logical or of the first and second argument, so if either are true then the result is true, otherwise it is false. | or(boolean, boolean) | or(true, false) = true and(true, true) = true or(field(‘first test’), field(‘second test’))  
not equal `!=` | Returns if its two arguments have different values. | any != any not_equal(any, any) | 1!=2 ‘a’ != 'b’  
not | Returns false if the argument is true and true if the argument is false. | not(boolean) | not(true) = false not(10=2) = true  
less than or equal `<=` | Returns true if the first argument less than or equal to the second, otherwise false. | any <= any | 1 <= 1 = true if(field(‘a’) <= field(‘b’), ‘a smaller’, ‘b is greater than or equal’)  
less than `<` | Returns true if the first argument less than the second, otherwise false. | any < any | 2 < 1 = false if(field(‘a’) < field(‘b’), ‘a is smaller’, ‘b is bigger or equal’)  
isblank | Returns true if the argument is empty or blank, false otherwise. | isblank(any) | isblank(‘10’)  
if | If the first argument is true then returns the second argument, otherwise returns the third. | if(bool, any, any) | if(field(‘text field’) = ‘on’, ‘it is on’, ‘it is off’)  
greater than or equal `>=` | Returns true if the first argument is greater than or equal to the second, otherwise false. | any >= any | 1 >= 1 = true if(field(‘a’) >= field(‘b’), ‘a is bigger or equal’, ‘b is smaller’)  
greater than `>` | Returns true if the first argument greater than the second, otherwise false. | any > any | 1 > 2 = false if(field(‘a’) > field(‘b’), ‘a is bigger’, ‘b is bigger or equal’)  
equal `=` | Returns if its two arguments have the same value. | any = any equal(any, any) | 1=1 ‘a’ = ‘a’  
and | Returns the logical and of the first and second argument, so if they are bothtrue then the result is true, otherwise it is false. | and(boolean, boolean) | and(true, false) = false and(true, true) = true and(field(‘first test’), field(‘second test’))  
is null | Returns true if the argument is null, false otherwise | is_null(any) | is_null(‘10’)  
  
|  |  |   
  
## Number functions

Functions | Details | Syntax | Examples  
---|---|---|---  
tonumber | Converts the input to a number if possible. | tonumber(text) | tonumber(‘10’) = 10  
sqrt | Returns the square root of the argument provided. | sqrt(number) | sqrt(9) = 3  
least | Returns the smallest of the two inputs. | least(number, number) | least(1,2) = 1  
greatest | Returns the greatest value of the two inputs. | greatest(number, number) | greatest(1,2) = 2  
divide `/` | Returns its two arguments divided, the first divided by the second. | number / number divide(number, number) | 10/2 = 5  
abs | Returns the absolute value for the argument number provided. | abs(number) | abs(1.49) = 1.49  
ceil | Returns the smallest integer that is greater than or equal the argument number provided. | ceil(number) | ceil(1.49) = 2  
even | Returns true if the argument provided is an even number, false otherwise. | even(number) | even(2) = true  
exp | Returns the result of the constant e ≈ 2.718 raised to the argument number provided. | exp(number) | exp(1.000) = 2.718  
floor | Returns the largest integer that is less than or equal the argument number provided. | floor(number) | floor(1.49) = 1  
is nan | Returns true if the argument is ‘NaN’, returns false otherwise. | is_nan(number) | is_nan(1 / 0) = true  
ln | Natural logarithm function: returns the exponent to which the constant e ≈ 2.718 must be raised to produce the argument. | ln(number) | ln(2.718) = 1.000  
log | Logarithm function: returns the exponent to which the first argument must be raised to produce the second argument. | log(number, number) | log(3, 9) = 2  
mod | Returns the remainder of the division between the first argument and the second argument. | mod(number, number) | mod(5, 2) = 1  
multiply `*` | Returns its two arguments multiplied together. | multiply(number, number) | 2*5 = 10  
odd | Returns true if the argument provided is an odd number, false otherwise. | odd(number) | odd(2) = false  
power | Returns the result of the first argument raised to the second argument exponent. | power(number, number) | power(3, 2) = 9  
round | Returns first argument rounded to the number of digits specified by the second argument. | round(number, number) | round(1.12345,2) = 1.12  
sign | Returns 1 if the argument is a positive number, -1 if the argument is a negative one, 0 otherwise. | sign(number) | sign(2.1234) = 1  
trunc | Returns only the first argument converted into an integer by truncating any decimal places. | trunc(number) | trunc(1.49) = 1  
when nan | Returns the first argument if it’s not ‘NaN’. Returns the second argument if the first argument is ‘NaN’ | when_nan(number, fallback) | when_nan(1 / 0, 4) = 4  
  
|  |  |   
  
## Text functions

Functions | Details | Syntax | Examples  
---|---|---|---  
upper | Returns its argument in upper case. | upper(text) | upper(‘a’) = ‘A’  
trim | Removes all whitespace from the left and right sides of the input. | trim(text) | trim(" abc ") = “abc”  
totext | Converts the input to text. | totext(any) | totext(10) = ‘10’  
t | Returns the arguments value if it is text, but otherwise ‘’. | t(any) | t(10)  
search | Returns a positive integer starting from 1 for the first occurrence of the second argument inside the first, or 0 if no occurrence is found. | search(text, text) | search(“test a b c test”, “test”) = 1 search(“none”, “test”) = 0  
right | Extracts the right most characters from the first input, stops when it has extracted the number of characters specified by the second input. | right(text, number) | right(“abcd”, 2) = “cd”  
reverse | Returns the reversed text of the provided first argument. | reverse(text) | reverse(“abc”) = “cba”  
replace | Replaces all instances of the second argument in the first argument with the third argument. | replace(text, text, text) | replace(“test a b c test”, “test”, “1”) = “1 a b c 1”  
regex replace | Replaces any text in the first input which matches the regex specified by the second input with the text in the third input. | regex_replace(text, regex text, replacement text) | regex_replace(“abc”, “a”, “1”) = “1bc”  
lower | Returns its argument in lower case. | lower(text) | lower(‘A’) = ‘a’  
length | Returns the number of characters in the first argument provided. | length(text) | length(“abc”) = 3  
left | Extracts the left most characters from the first input, stops when it has extracted the number of characters specified by the second input. | left(text, number) | left(“abcd”, 2) = “ab”  
contains | Returns true if the first piece of text contains at least once the second. | contains(text,text) | contains(“test”, “e”) = true  
concat | Returns its arguments joined together as a single piece of text. | concat(any, any, …) | concat(‘A’, 1, 1=2) = ‘A1false’  
  
## Troubleshooting   
### Boolean functions not working well with fields as arguments 

Formula functions, for example, `isblank()`, or `when_empty` work with simple values like [text, number, or date](/user-docs/baserow-field-overview) fields. Computed fields like [Link-to-table](/user-docs/link-to-table-field), [look-up](/user-docs/lookup-field), and [rollup fields](/user-docs/rollup-field) can contain multiple items which makes them arrays or lists.

To create formulas to make a Boolean test on data in field C, taking data from field A if it’s TRUE, otherwise taking data from field B if it’s FALSE, you need to convert any array to text using the `join()` function. For example:

![Baserow boolean](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/fbc9bcfe-b256-418e-877a-9d701ba723b0/boolean.png)

`if(isblank(join(field('Organization'),'')), field('Notes'), field('Name'))`

Using `join()` to convert the list to text, handles the empty scenario correctly. This formula checks if the _Organization_ field (a link-to-table field) has a value. If it’s true, it shows the content of the _Name_ field; otherwise, it displays the content of the _Notes_ field.

### Is it possible to check if a date is a specific day of the week?

Yes, you can check if a date field is a specific day of the week in Baserow using a formula. Here’s how: `datetime_format(field('date field'), 'D') = '1'`

  * `field('date field')`: This retrieves the value from the date field in your Baserow table.
  * `datetime_format(..., 'D')`: This function formats the date value according to the specified format code ‘D’. In this case, ‘D’ represents the day of the week (Sunday = 1, Monday = 2, etc.).
  * `= '1'`: This compares the formatted day of the week (a number) with the number 1 (representing Sunday). You can replace ‘1’ with any other number to check for a different day (e.g., ‘2’ for Monday).

The formula will evaluate to `TRUE` if the date in the date field is Sunday, and `FALSE` otherwise.

You can find more information about the `datetime_format` function and other formatting options in the [Baserow documentation](/user-docs/understanding-formulas#date-and-time-functions).

For a deeper understanding of formatting options available for the `datetime_format` function, you can refer to the documentation on [PostgreSQL formatting functions](https://www.postgresql.org/docs/current/functions-formatting.html).   

## Related content

  * [Understand Baserow formulas and how to use formulas](/docs/tutorials/understanding-baserow-formulas)
  * [Formula field overview](/user-docs/formula-field-overview)
  * [Technical understanding of how Baserow formulas are implemented](/docs/technical/formula-technical-guide)
  * [Generate formulas with AI](/user-docs/generate-formulas-with-baserow-ai)

