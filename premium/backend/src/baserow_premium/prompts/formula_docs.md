# Baserow Formula Language Documentation

## Introduction

A Baserow Formula field lets you create a field whose contents are calculated based on a Baserow Formula you've provided. A Baserow Formula is simply some text written in a particular way such that Baserow can understand it, for example the text `1+1` is a Baserow formula which will calculate the result `2` for every row.

### Simple Formula Example

Imagine you have a table with a normal text field called `text field` with 3 rows containing the text `one`, `two` and `three` respectively. If you then create a formula field with the formula `concat('Number', field('text field'))` the resulting table would look like:

| text field | formula field |
| ---------- | ------------- |
| one        | Number one    |
| two        | Number two    |
| three      | Number three  |

### Breaking Down a Simple Formula

Let's split apart the formula `concat('Number', field('text field'))` to understand what is going on:

-   `concat`: Concat is one of many formula functions you can use. It will join together all the inputs you give to it into one single piece of text.
-   `(`: To give inputs to a formula function you first have to write an opening parenthesis indicating the inputs will follow.
-   `'Number'`: This is the first input we are giving to concat and it is literally just the text Number. When writing literal pieces of text in a formula you need to surround them with quotes.
-   `,`: As we are giving multiple inputs to concat we need to separate each input with a comma.
-   `field('text field')`: This is the second and final input we are giving to concat. We could keep on adding however many inputs as we wanted however as long as each was separated by a comma. This second input is a reference to the field in the same table with the name text field. For each cell in the formula field this reference will be replaced by whatever the value in the text field field is for that row.
-   `)`: Finally, we need to tell Baserow we've finished giving inputs to the concat function, we do this with a matching closing parenthesis.

### What is a Formula Function?

A function in a formula takes a number of inputs depending on the type of the function. It does some calculation using those inputs and produces an output. Functions also sometimes only take specific types of inputs. For example the `datetime_format` only accepts two inputs, the first must be a date (either a field reference to a date field or a sub formula which calculates a date) and the second must be some text.

All the available functions for you to use are shown in the expanded formula edit box which appears when you click on the formula whilst editing a formula field.

## Working with Different Data Types

### Using Numbers in Formulas

Formulas can be used to do numerical calculations. The standard maths operators exist like `+`, `-`, `*` and `/`. You can use whole numbers or decimal numbers directly in your formula like so: `(field('number field') + 10.005)/10`

### Using Dates

Use the `todate` function to create a constant date inside a formula like so: `todate('2020-01-01 10:20:30', 'YYYY-MM-DD HH:MI:SS')`. The first argument is the date you want in text form and the second is the format of the date text.

### Using Date Intervals

Subtracting two dates returns a duration representing the difference in time between the two dates: `field('date a') - field('date b')`. The `date_interval` function lets you create intervals inside the formula to work with.

Multiplying a duration and a number the result will be a duration where the number of seconds are multiplied for the number argument.

Need to calculate a new date based on a date/time interval? Use the `date_interval` function like so: `field('my date column') - date_interval('1 year')`

### Conditional Calculations

If you need to do a calculation conditionally then the `if` function and comparison operators will let you do this. For example the following formula calculates whether a date field is the first day of a month: `if(day(field('some date')) = 1, true, false)`.

You can compare fields and sub-formulas using the `>`, `>=`, `<=`, `<`, `=` and `!=` operators.

### Working with Arrays and Computed Fields

Formula functions, for example, `isblank()` or `when_empty()` work with simple values like text, number, or date fields. Computed fields like Link-to-table, look-up, and rollup fields can contain multiple items which makes them arrays or lists.

To create formulas to make a Boolean test on data in field C, taking data from field A if it's TRUE, otherwise taking data from field B if it's FALSE, you need to convert any array to text using the `join()` function. For example: `if(isblank(join(field('Organization'),'')), field('Notes'), field('Name'))`.

Using `join()` to convert the list to text handles the empty scenario correctly. This formula checks if the Organization field (a link-to-table field) has a value. If it's true, it shows the content of the Name field; otherwise, it displays the content of the Notes field.

## Function Reference

### Text Functions

| Functions            | Details                                                                                                                                               | Syntax                                            | Examples                                                                           |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- | ---------------------------------------------------------------------------------- |
| concat               | Returns its arguments joined together as a single piece of text.                                                                                      | concat(any, any, ...)                             | concat('A', 1, 1=2) = 'A1false'                                                    |
| upper                | Returns its argument in upper case.                                                                                                                   | upper(text)                                       | upper('a') = 'A'                                                                   |
| lower                | Returns its argument in lower case.                                                                                                                   | lower(text)                                       | lower('A') = 'a'                                                                   |
| trim                 | Removes all whitespace from the left and right sides of the input.                                                                                    | trim(text)                                        | trim(" abc ") = "abc"                                                              |
| totext               | Converts the input to text.                                                                                                                           | totext(any)                                       | totext(10) = '10'                                                                  |
| t                    | Returns the arguments value if it is text, but otherwise ''.                                                                                          | t(any)                                            | t(10)                                                                              |
| length               | Returns the number of characters in the first argument provided.                                                                                      | length(text)                                      | length("abc") = 3                                                                  |
| reverse              | Returns the reversed text of the provided first argument.                                                                                             | reverse(text)                                     | reverse("abc") = "cba"                                                             |
| left                 | Extracts the left most characters from the first input, stops when it has extracted the number of characters specified by the second input.           | left(text, number)                                | left("abcd", 2) = "ab"                                                             |
| right                | Extracts the right most characters from the first input, stops when it has extracted the number of characters specified by the second input.          | right(text, number)                               | right("abcd", 2) = "cd"                                                            |
| search               | Returns a positive integer starting from 1 for the first occurrence of the second argument inside the first, or 0 if no occurrence is found.          | search(text, text)                                | search("test a b c test", "test") = 1 search("none", "test") = 0                   |
| contains             | Returns true if the first piece of text contains at least once the second.                                                                            | contains(text,text)                               | contains("test", "e") = true                                                       |
| replace              | Replaces all instances of the second argument in the first argument with the third argument.                                                          | replace(text, text, text)                         | replace("test a b c test", "test", "1") = "1 a b c 1"                              |
| regex_replace        | Replaces any text in the first input which matches the regex specified by the second input with the text in the third input.                          | regex_replace(text, regex text, replacement text) | regex_replace("abc", "a", "1") = "1bc"                                             |
| split_part           | Extracts a segment from a delimited string based on a delimiter and index (numeric indicator indicating which element from string should be returned) | split_part(text, delimiter, position)             | split_part('John, Jane, Michael', ', ', 2) = 'Jane'                                |
| encode_uri           | Returns a encoded URI string from the argument provided.                                                                                              | encode_uri(text)                                  | encode_uri('http://example.com/wiki/Señor') = 'http://example.com/wiki/Se%c3%b1or' |
| encode_uri_component | Returns a encoded URI string component from the argument provided.                                                                                    | encode_uri_component(text)                        | encode_uri_component('Hello World') = 'Hello%20World'                              |
| tourl                | Converts the input to url.                                                                                                                            | tourl(any)                                        | tourl('www.baserow.io') = 'www.baserow.io'                                         |

### Number Functions

| Functions | Details                                                                                                                  | Syntax                     | Examples                |
| --------- | ------------------------------------------------------------------------------------------------------------------------ | -------------------------- | ----------------------- |
| tonumber  | Converts the input to a number if possible.                                                                              | tonumber(text)             | tonumber('10') = 10     |
| abs       | Returns the absolute value for the argument number provided.                                                             | abs(number)                | abs(1.49) = 1.49        |
| ceil      | Returns the smallest integer that is greater than or equal the argument number provided.                                 | ceil(number)               | ceil(1.49) = 2          |
| floor     | Returns the largest integer that is less than or equal the argument number provided.                                     | floor(number)              | floor(1.49) = 1         |
| round     | Returns first argument rounded to the number of digits specified by the second argument.                                 | round(number, number)      | round(1.12345,2) = 1.12 |
| trunc     | Returns only the first argument converted into an integer by truncating any decimal places.                              | trunc(number)              | trunc(1.49) = 1         |
| sqrt      | Returns the square root of the argument provided.                                                                        | sqrt(number)               | sqrt(9) = 3             |
| power     | Returns the result of the first argument raised to the second argument exponent.                                         | power(number, number)      | power(3, 2) = 9         |
| exp       | Returns the result of the constant e ≈ 2.718 raised to the argument number provided.                                     | exp(number)                | exp(1.000) = 2.718      |
| ln        | Natural logarithm function: returns the exponent to which the constant e ≈ 2.718 must be raised to produce the argument. | ln(number)                 | ln(2.718) = 1.000       |
| log       | Logarithm function: returns the exponent to which the first argument must be raised to produce the second argument.      | log(number, number)        | log(3, 9) = 2           |
| mod       | Returns the remainder of the division between the first argument and the second argument.                                | mod(number, number)        | mod(5, 2) = 1           |
| sign      | Returns 1 if the argument is a positive number, -1 if the argument is a negative one, 0 otherwise.                       | sign(number)               | sign(2.1234) = 1        |
| even      | Returns true if the argument provided is an even number, false otherwise.                                                | even(number)               | even(2) = true          |
| odd       | Returns true if the argument provided is an odd number, false otherwise.                                                 | odd(number)                | odd(2) = false          |
| greatest  | Returns the greatest value of the two inputs.                                                                            | greatest(number, number)   | greatest(1,2) = 2       |
| least     | Returns the smallest of the two inputs.                                                                                  | least(number, number)      | least(1,2) = 1          |
| is_nan    | Returns true if the argument is 'NaN', returns false otherwise.                                                          | is_nan(number)             | is_nan(1 / 0) = true    |
| when_nan  | Returns the first argument if it's not 'NaN'. Returns the second argument if the first argument is 'NaN'                 | when_nan(number, fallback) | when_nan(1 / 0, 4) = 4  |

### Arithmetic Operators

| Functions    | Details                                                             | Syntax                                                                                              | Examples                                                            |
| ------------ | ------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| add `+`      | Returns its two arguments added together.                           | number + number text + text date + duration duration + duration duration + date add(number, number) | 1+1 = 2 'a' + 'b' = 'ab'                                            |
| minus `-`    | Returns its two arguments subtracted.                               | number - number minus(number, number) date - date date - duration duration - duration               | 3-1 = 2                                                             |
| multiply `*` | Returns its two arguments multiplied together.                      | multiply(number, number) multiply(duration, number)                                                 | 2*5 = 10 date_interval('1 second') * 60 = date_interval('1 minute') |
| divide `/`   | Returns its two arguments divided, the first divided by the second. | number / number duration / number divide(number, number)                                            | 10/2 = 5 date_interval('1 minute') / 60 = date_interval('1 second') |

### Date and Time Functions

Build more powerful formulas around dates in Baserow. The `today()` and `now()` functions update every 10 minutes.

The `today()` function is useful for calculating intervals or when you need to have the current date displayed on a table. The `now()` function is useful when you need to display the current date and time on your table or calculate a value based on the current date and time, and have that value updated each time you open your database.

| Functions          | Details                                                                                                                                                                                               | Syntax                               | Examples                                                                                     |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------ | -------------------------------------------------------------------------------------------- |
| now                | Returns the current date and time in utc.                                                                                                                                                             | now()                                | now() > todate("2021-12-12 13:00:00", "YYYY-MM-DD HH24:MI:SS")                               |
| today              | Returns the current date in utc.                                                                                                                                                                      | today()                              | today() > todate("2021-12-12", "YYYY-MM-DD")                                                 |
| todate             | Returns the first argument converted into a date given a date format string as the second argument.                                                                                                   | todate(text, text)                   | todate('20210101', 'YYYYMMDD')                                                               |
| todate_tz          | Returns the first argument converted into a date given a date format string as the second argument and the timezone provided as third argument.                                                       | todate_tz(text, text, text)          | todate_tz("2021-12-12 13:00:00", "YYYY-MM-DD HH24:MI:SS", "America/New_York")                |
| datetime_format    | Converts the date to text given a way of formatting the date.                                                                                                                                         | datetime_format(date, text)          | datetime_format(field('date field'), 'YYYY')                                                 |
| datetime_format_tz | Returns the first argument converted into a date given a date format string as the second argument and the timezone provided as third argument.                                                       | datetime_format_tz(date, text, text) | datetime_format_tz(field('date field'), 'YYYY', 'Europe/Rome')                               |
| year               | Returns the number of years in the provided date.                                                                                                                                                     | year(date)                           | year(field("my date"))                                                                       |
| month              | Returns the number of months in the provided date.                                                                                                                                                    | month(date)                          | month(todate("2021-12-12", "YYYY-MM-DD")) = 12                                               |
| day                | Returns the day of the month as a number between 1 to 31 from the argument.                                                                                                                           | day(date)                            | day(todate('20210101', 'YYYYMMDD')) = 1                                                      |
| second             | Returns the number of seconds in the provided date.                                                                                                                                                   | second(date)                         | second(field("dates")) == 2                                                                  |
| date_diff          | Given a date unit to measure in as the first argument ('year', 'month', 'week', 'day', 'hour', 'minute', 'seconds') calculates and returns the number of units from the second argument to the third. | date_diff(text, date, date)          | date_diff('yy', todate('2000-01-01', 'YYYY-MM-DD'), todate('2020-01-01', 'YYYY-MM-DD')) = 20 |
| date_interval      | Returns the date interval corresponding to the provided argument.                                                                                                                                     | date_interval(text)                  | date_interval('1 year') date_interval('2 seconds')                                           |
| toduration         | Converts the number of seconds provided into a duration.                                                                                                                                              | toduration(number)                   | toduration(3600) = date_interval('1 hour')                                                   |
| toseconds          | Converts the duration provided into the corresponding number of seconds.                                                                                                                              | toseconds(duration)                  | toseconds(date_interval('1 hour')) == 3600                                                   |

### Boolean Functions

| Functions                  | Details                                                                                                                            | Syntax                         | Examples                                                                                       |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- | ------------------------------ | ---------------------------------------------------------------------------------------------- |
| if                         | If the first argument is true then returns the second argument, otherwise returns the third.                                       | if(bool, any, any)             | if(field('text field') = 'on', 'it is on', 'it is off')                                        |
| equal `=`                  | Returns if its two arguments have the same value.                                                                                  | any = any equal(any, any)      | 1=1 'a' = 'a'                                                                                  |
| not_equal `!=`             | Returns if its two arguments have different values.                                                                                | any != any not_equal(any, any) | 1!=2 'a' != 'b'                                                                                |
| greater_than `>`           | Returns true if the first argument greater than the second, otherwise false.                                                       | any > any                      | 1 > 2 = false if(field('a') > field('b'), 'a is bigger', 'b is bigger or equal')               |
| greater_than_or_equal `>=` | Returns true if the first argument is greater than or equal to the second, otherwise false.                                        | any >= any                     | 1 >= 1 = true if(field('a') >= field('b'), 'a is bigger or equal', 'b is smaller')             |
| less_than `<`              | Returns true if the first argument less than the second, otherwise false.                                                          | any < any                      | 2 < 1 = false if(field('a') < field('b'), 'a is smaller', 'b is bigger or equal')              |
| less_than_or_equal `<=`    | Returns true if the first argument less than or equal to the second, otherwise false.                                              | any <= any                     | 1 <= 1 = true if(field('a') <= field('b'), 'a smaller', 'b is greater than or equal')          |
| and                        | Returns the logical and of the first and second argument, so if they are both true then the result is true, otherwise it is false. | and(boolean, boolean)          | and(true, false) = false and(true, true) = true and(field('first test'), field('second test')) |
| or                         | Returns the logical or of the first and second argument, so if either are true then the result is true, otherwise it is false.     | or(boolean, boolean)           | or(true, false) = true or(true, true) = true or(field('first test'), field('second test'))     |
| not                        | Returns false if the argument is true and true if the argument is false.                                                           | not(boolean)                   | not(true) = false not(10=2) = true                                                             |
| isblank                    | Returns true if the argument is empty or blank, false otherwise.                                                                   | isblank(any)                   | isblank('10')                                                                                  |
| is_null                    | Returns true if the argument is null, false otherwise                                                                              | is_null(any)                   | is_null('10')                                                                                  |

### Aggregate Functions

These functions work with arrays and lookup values to perform calculations across multiple values.

| Functions       | Details                                                                                                                                                                                                                        | Syntax                                                                          | Examples                                                                                                                                                                                                                              |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| sum             | Sums all of the values and returns the result.                                                                                                                                                                                 | sum(numbers from lookup() or field())                                           | sum(lookup("link field", "number field")) sum(lookup("link field", "duration field")) sum(field("lookup field")) sum(field("link field with number primary field"))                                                                   |
| avg             | Averages all of the values and returns the result.                                                                                                                                                                             | avg(numbers from lookup() or field())                                           | avg(lookup("link field", "number field")) avg(lookup("link field", "duration field")) avg(field("lookup field")) avg(field("link field with number primary field"))                                                                   |
| count           | Returns the number of items in its first argument.                                                                                                                                                                             | count(array)                                                                    | count(field('my link row field'))                                                                                                                                                                                                     |
| min             | Returns the smallest number from all the looked up values provided.                                                                                                                                                            | min(numbers from a lookup() or field())                                         | min(lookup("link field", "number field")) min(lookup("link field", "duration field")) min(field("lookup field")) min(field("link field with text primary field"))                                                                     |
| max             | Returns the largest number from all the looked up values provided.                                                                                                                                                             | max(numbers from a lookup() or field())                                         | max(lookup("link field", "number field")) max(lookup("link field", "duration field")) max(field("lookup field")) max(field("link field with text primary field"))                                                                     |
| stddev_sample   | Calculates the sample standard deviation of the values and returns the result. The sample deviation should be used when the provided values are only for a sample or subset of values for an underlying population.            | stddev_sample(numbers from lookup() or field())                                 | stddev_sample(lookup("link field", "number field")) stddev_sample(lookup("link field", "duration field")) stddev_sample(field("lookup field")) stddev_sample(field("link field with number primary field"))                           |
| stddev_pop      | Calculates the population standard deviation of the values and returns the result. The population standard deviation should be used when the provided values contain a value for every single piece of data in the population. | stddev_pop(numbers from lookup() or field())                                    | stddev_pop(lookup("link field", "number field")) stddev_pop(lookup("link field", "duration field")) stddev_pop(field("lookup field")) stddev_pop(field("link field with number primary field"))                                       |
| variance_sample | Calculates the sample variance of the values and returns the result. The sample variance should be used when the provided values are only for a sample or subset of values for an underlying population.                       | variance_sample(numbers from lookup() or field())                               | variance_sample(lookup("link field", "number field")) variance_sample(field("lookup field")) variance_sample(field("link field with number primary field"))                                                                           |
| variance_pop    | Calculates the population variance of the values and returns the result. The population variance should be used when the provided values contain a value for every single piece of data in the population.                     | variance_pop(numbers from lookup() or field())                                  | variance_pop(lookup("link field", "number field")) variance_pop(field("lookup field")) variance_pop(field("link field with number primary field"))                                                                                    |
| join            | Concats all of the values from the first input together using the values from the second input.                                                                                                                                | join(text from lookup() or field(), text)                                       | join(lookup("link field", "number field"), "\_") join(field("lookup field"), field("different lookup field")) join(field("link field with text primary field"), ",")                                                                  |
| filter          | Filters down an expression involving a lookup/link field reference or a lookup function call.                                                                                                                                  | filter(an expression involving lookup() or field(a link/lookup field), boolean) | sum(filter(lookup("link field", "number field"), lookup("link field", "number field") > 10)) filter(field("lookup field"), contains(field("lookup field"), "a")) filter(field("link field") + "a", length(field("link field")) > 10") |
| every           | Returns true if every one of the provided looked up values is true, false otherwise.                                                                                                                                           | every(boolean values from a lookup() or field())                                | every(field("my lookup") = "test")                                                                                                                                                                                                    |
| any             | Returns true if any one of the provided looked up values is true, false if they are all false.                                                                                                                                 | any(boolean values from a lookup() or field())                                  | any(field("my lookup") = "test")                                                                                                                                                                                                      |

### Special Functions

| Functions  | Details                                                                                                                                                                                                                          | Syntax                                                                               | Examples                                                                                                                    |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------- |
| field      | Returns the field named by the single text argument.                                                                                                                                                                             | field('a field name')                                                                | field('my text field') = 'flag'                                                                                             |
| lookup     | Looks up the values from a field in another table for rows in a link row field. The first argument should be the name of a link row field in the current table and the second should be the name of a field in the linked table. | lookup('a link row field name', 'field name in other the table')                     | lookup('link row field', 'first name') = lookup('link row field', 'last name')                                              |
| row_id     | Returns the rows unique identifying number.                                                                                                                                                                                      | row_id()                                                                             | concat("Row ", row_id())                                                                                                    |
| when_empty | If the first input is calculated to be empty the second input will be returned instead, otherwise if the first input is not empty the first will be returned.                                                                    | when_empty(any, same type as the first)                                              | when_empty(field("a"), "default")                                                                                           |
| has_option | Returns true if the first argument is a multiple select field or a lookup to a single select field and the second argument is one of the options.                                                                                | has_option(multiple select, text); has_option(lookup(link row, single select), text) | has_option(field('multiple select'), 'option_a'); has_option(lookup(field('link row'), field('single select')), 'option_a') |

### URL Functions

| Functions      | Details                                                                      | Syntax                 | Examples                                                                |
| -------------- | ---------------------------------------------------------------------------- | ---------------------- | ----------------------------------------------------------------------- |
| link           | Creates a hyperlink using the URI provided in the first argument.            | link(text)             | link('http://your-text-here.com')                                       |
| button         | Creates a button using the URI (first argument) and label (second argument). | button(text, text)     | button('http://your-text-here.com', 'your-label')                       |
| get_link_url   | Gets the url from a formula using the link or button functions.              | get_link_url(link)     | get_link_url(field('formula link field')) = 'http://your-text-here.com' |
| get_link_label | Gets the label from a formula using the link or button functions.            | get_link_label(button) | get_link_label(field('formula button field')) = 'your-label'            |

### File Functions

| Functions             | Details                                                                            | Syntax                        | Examples                                             |
| --------------------- | ---------------------------------------------------------------------------------- | ----------------------------- | ---------------------------------------------------- |
| get_file_count        | Returns the number of files in a file field.                                       | get_file_count(a file field)  | get_file_count(field("File field"))                  |
| get_file_size         | Returns the file size from a single file returned from the index function.         | get_file_size(a file)         | get_file_size(index(field("File field"), 0))         |
| get_file_visible_name | Returns the visible file name from a single file returned from the index function. | get_file_visible_name(a file) | get_file_visible_name(index(field("File field"), 0)) |
| get_file_mime_type    | Returns the file mime type from a single file returned from the index function.    | get_file_mime_type(a file)    | get_file_mime_type(index(field("File field"), 0))    |
| get_image_width       | Returns the image width from a single file returned from the index function.       | get_image_width(a file)       | get_image_width(index(field("File field"), 0))       |
| get_image_height      | Returns the image height from a single file returned from the index function.      | get_image_height(a file)      | get_image_height(index(field("File field"), 0))      |
| is_image              | Returns if the single file returned from the index function is an image or not.    | is_image(a file)              | is_image(index(field("File field"), 0))              |
