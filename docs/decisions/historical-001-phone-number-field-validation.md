# How to Validate and Format Phone Number Fields 

See this issue for background: https://gitlab.com/baserow/baserow/-/issues/339

For the new number phone number field there are a number of options around how to
validate and format the field. This document captures

# Decision

Option 1 was chosen because:

-   It is the simplest and there are no specific user requests for any of the more complex
    options below, so instead we stick to the simple option.
-   We do not need to reason about the validation provided by two different open source
    libraries and test that they agree which numbers are valid or not.

## Option 1:

Use a simple regex only allowing numbers, spaces and some punctuation to validate phone
numbers. Assume every entered phone number which passes this regex is a valid number and
display the number as a link (href="tel: {{value}}")
when appropriate so the user can call the number.

### Pros:

-   Simplest technically
-   No need to use external libraries
-   Most flexible for the user as they can enter any type of telephone format
-   We might be able to pass on this "validate the phone number" problem to the phone as
    if it is formatted as a href="tel: xxx" link the phone might then format the opened
    link

### Cons:

-   Users can easily enter complete nonsense for phone numbers
-   Its upto the user to nicely format the phone numbers every single time

## Option 2:

Use a [python](https://github.com/daviddrysdale/python-phonenumbers)
and [js library](https://github.com/catamphetamine/libphonenumber-js) both based
off [google's phonenumberlib](https://github.com/google/libphonenumber) and validate
that a number is "possible" which is a lower standard and less likely to change compared
to "
valid". Auto format the number based on it could be using any country code.

### Pros

-   Dont need to store/allow configuring extra country code information
-   Nice formatting for international numbers
-   By using the least strict form of validation provided by the libraries we can be more
    sure that the validations match between client and server.

### Cons

-   Dont get nice country specific formatting unless the user enters a country code in the
    number itself as otherwise the libraries cant detect what the country is.

## Option 3:

Option 2 but also allow user to specify a country code OR "international" on the whole
field, format and validate numbers entered using this country code.

### Pros

-   Get nice formatting for local numbers if you set the column

### Cons

-   Limits users to only having one telephone format per column, cant mix numbers without
    using international
-   Have to implement / design a country code select mechanism
-   Have to store and sync extra country code data on the field

## Option 4:

Option 2, but also allow user to set a default country code on the field and then let
the user pick a country code per row which defaults to the fields default.

### Pros

-   Users can mix every possible type of phone number in a single field and get nice
    formatting and validation.
-   If they dont want to mix then they can fallback to option 2 by using a default code
-   If they dont want any country specific formatting they can fallback to option 1

### Cons

-   Have to store country data per field and row
-   Have to design a row entry component which uses the default + lets users pick a
    country code per field + column

## Option 5:

Only use a front-end library to format the entered phone numbers and check they are
posible purely in the front-end, the backend does simple or no validation.

### Pros

-   Don't need to worry about syncing the front and back end validation
-   Still get nice phone number entry and formatting

### Cons

-   When a user converts a non-phone number field to being a phone number this happens on
    the backend and hence no nice formatting will happen. Then when the user edits one
    of these unformatted cells it will instantly change to be formatted.
