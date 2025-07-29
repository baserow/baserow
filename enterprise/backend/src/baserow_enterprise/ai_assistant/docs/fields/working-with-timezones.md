# Baserow Documentation

Source: https://baserow.io/user-docs/working-with-timezones

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# Working with timezones

This section will cover how to use timezones in Baserow.

In Baserow, all dates are stored in the UTC timezone by default. You can select the date format, time format and choose a timezone for your date field types on a field-by-field basis.

You can enable the following functionality:

  * choose if you want to see timezones or not in the date field types.
  * copy & paste and export include a timezone in the exported value if “Show timezone” is checked.
  * use the `now` timezones to filter table data based on the date fields.

![Working with timezones](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/4e9d182b-07de-43f4-8014-058bf7b55356/London.webp)

## Displaying dates

Baserow stores all dates in Coordinated Universal Time, or UTC. However, the [Date and Time Field](/user-docs/date-and-time-fields) configuration that determines how the date appears in the table will apply to all workspace collaborators.

Depending on whether a certain timezone has been selected for a [datetime field type](/user-docs/date-and-time-fields), collaborators working together in the same base can either view the same dates and times or different dates and times.

Dates can be displayed in two ways:

  * Set the date in the user’s timezone, so that the datetime appears differently for users in different timezones. The formatted date will be set to any user’s local time.
  * Set the same timezone to show a specific timezone for all collaborators in your workspace.

![Displaying dates](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/358abe1d-e7f0-4e81-92ee-935c4593125b/Screenshot_2023-03-08_at_14.32.57.png)

## Set timezone for a date field

There are two methods for specifying a timezone for a date field.

  * Check the “Set timezone for all collaborators” option in the [field configuration menu](/user-docs/field-customization) and select the timezone.
  * Use a formula field with the `todate_tz` function.

### Set a timezone in the date field configuration menu

You can specify a timezone for a date field for all collaborators by selecting the “Set timezone for all collaborators” option from the [field configuration menu](/user-docs/field-customization). You’ll then be able to select your preferred timezone from the drop-down options. The default timezone is GMT/UTC.

![Set a timezone in the date field configuration menu](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/bcdfa752-0ce8-4759-b7af-0189621f3cfb/Screenshot_2023-03-31_at_01.31.18.png)

### Set a timezone with a `todate_tz` formula function

This can be used to display multiple time zones based on predefined conditions.

The `todate_tz` function returns the first argument converted into a date given a date format string as the second argument and the timezone provided as the third argument.

This is written in the form `todate_tz('date', 'dateformat', 'timezone')`, in which the timezone can be something like `'Pacific/Fiji'`, `'Europe/London'`, or `'Canada/Central'`.

> For a list of supported time zones, see this section on supported timezones. For a full list of supported date formats, see this section on [setting a date format](/user-docs/date-and-time-fields#setting-a-date-format).
    
    
    todate_tz('20210101', 'YYYYMMDD', 'Europe/Amsterdam')
    

## Supported timezones

The default timezone for the date type field in Baserow matches the locale on the device you are using.

If you want to switch from one timezone to another, Baserow will do an automatic conversion in a few seconds.

You can display the same time for all collaborators across timezones by selecting the **Set timezone for all collaborators** option in the field’s customisation menu. This will make the timezone the same for everyone.

![Supported timezones](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/7c8c5b29-a10f-46e7-ae78-70200d0d0a28/Untitled.png)

The timezone dropdown option lets you specify the timezone for the date. The following is a list of supported timezones:

Africa/Abidjan

Africa/Accra

Africa/Addis_Ababa

Africa/Algiers

Africa/Asmara

Africa/Asmera

Africa/Bamako

Africa/Bangui

Africa/Banjul

Africa/Bissau

Africa/Blantyre

Africa/Brazzaville

Africa/Bujumbura

Africa/Cairo

Africa/Casablanca

Africa/Ceuta

Africa/Conakry

Africa/Dakar

Africa/Dar_es_Salaam

Africa/Djibouti

Africa/Doula

Africa/El_Aaiun

Africa/Freetown

Africa/Gaborone

Africa/Harare

Africa/Johannesburg

Africa/Juba

Africa/Kampala

Africa/Khartoum

Africa/Kigali

Africa/Kinshasha

Africa/Lagos

Africa/Libreville

Africa/Lome

Africa/Luanda

Africa/Lubumbashi

Africa/Lusaka

Africa/Malabo

Africa/Maputo

Africa/Maseru

Africa/Mbabane

Africa/Mogadishu

Africa/Monrovia

Africa/Nairobi

Africa/Ndjamena

Africa/Niamey

Africa/Nouakchott

Africa/Ouagadougou

Africa/Porto-Novo

Africa/Sao_Tome

Africa/Timbuktu

Africa/Tripoli

Africa/Tunis

Africa/Windhoek

America/Adak

America/Anchorage

America/Anguilla

America/Antigua

America/Araguaina

America/Argentina/Buenos_Aires

America/Argentina/Catamarca

America/Argentina/ComodRivadavia

America/Argentina/Cordoba

America/Argentina/Jujuy

America/Argentina/La_Rioja

America/Argentina/Mendoza

America/Argentina/Rio_Gallegos

America/Argentina/Salta

America/Argentina/San_Juan

America/Argentina/San_Luis

America/Argentina/Tucuman

America/Argentina/Ushuaia

America/Aruba

America/Asuncion

America/Atikokan

America/Atka

America/Bahia

America/Bahia_Banderas

America/Barbados

America/Belem

America/Belize

America/Blanc-Sablon

America/Boa_Vista

America/Bogota

America/Boise

America/Buenos Aires

America/Cambridge_Bay

America/Campo_Grande

America/Cancun

America/Caracas

America/Catamarca

America/Cayenne

America/Cayman

America/Chicago

America/Chihuahua

America/Coral_Harbour

America/Cordoba

America/Costa_Rica

America/Creston

America/Cuiaba

America/Curacao

America/Danmarkshavn

America/Dawson

America/Dawson_Creek

America/Denver

America/Detroit

America/Dominica

America/Edmonton

America/Eirunepe

America/El_Salvador

America/Ensenada

America/Fort_Nelson

America/Fort_Wayne

America/Fortaleza

America/Glace_Bay

America/Godthab

America/Goose_Bay

America/Grand_Turk

America/Grenada

America/Guadeloupe

America/Guatemala

America/Guayaquil

America/Guyana

America/Halifax

America/Havana

America/Hermosillo

America/Indiana/Indianapolis

America/Indiana/Knox

America/Indiana/Marengo

America/Indiana/Petersburg

America/Indiana/Tell_City

America/Indiana/Vevay

America/Indiana/Vincennes

America/Indiana/Winamac

America/Indianapolis

America/Inuvik

America/Iqaluit

America/Jamaica

America/Jujuy

America/Juneau

America/Kentucky/Louisville

America/Kentucky/Monticello

America/Knox_IN

America/Kralendijk

America/La_Paz

America/Lima

America/Los_Angeles

America/Louisville

America/Lower_Princes

America/Maceio

America/Managua

America/Manaus

America/Marigot

America/Martinique

America/Matamoros

America/Mazatlan

America/Mendoza

America/Menominee

America/Merida

America/Metlakatla

America/Mexico_City

America/Miquelon

America/Moncton

America/Monterrey

America/Montreal

America/Montserrat

America/Montevideo

America/Nassau

America/New_York

America/Nipigon

America/Nome

America/Noronha

America/North_Dakota/Beulah

America/North_Dakota/Center

America/North_Dakota/New_Salem

America/Ojinaga

America/Nuuk

America/Panama

America/Pangnirtung

America/Paramaribo

America/Phoenix

America/Port-au-Prince

America/Port_of_Spain

America/Porto_Acre

America/Porto_Velho

America/Puerto_Rico

America/Punta_Arenas

America/Rainy_River

America/Rankin_Inlet

America/Recife

America/Regina

America/Resolute

America/Rio_Branco

America/Rosario

America/Santa_Isabel

America/Santarem

America/Santiago

America/Santo_Domingo

America/Sao_Paulo

America/Scoresbysund

America/Shiprock

America/Sitka

America/St_Barthelemy

America/St_Johns

America/St_Kitts

America/St_Lucia

America/St_Thomas

America/St_Vincent

America/Swift_Current

America/Tegucigalpa

America/Thule

America/Thunder_Bay

America/Tijuana

America/Toronto

America/Tortola

America/Vancouver

America/Virgin

America/Whitehorse

America/Winnipeg

America/Yakutat

America/Yellowknife

‘Antarctica/Casey’,

‘Antarctica/Davis’,

‘Antarctica/DumontDUrville’,

‘Antarctica/Macquarie’,

‘Antarctica/Mawson’,

‘Antarctica/Palmer’,

‘Antarctica/Rothera’,

‘Antarctica/Syowa’,

‘Antarctica/Troll’,

‘Antarctica/Vostok’,

‘Asia/Almaty’,

‘Asia/Amman’,

‘Asia/Anadyr’,

‘Asia/Aqtau’,

‘Asia/Aqtobe’,

‘Asia/Ashgabat’,

‘Asia/Baghdad’,

‘Asia/Baku’,

‘Asia/Bangkok’,

‘Asia/Barnaul’,

‘Asia/Beirut’,

‘Asia/Bishkek’,

‘Asia/Brunei’,

‘Asia/Chita’,

‘Asia/Choibalsan’,

‘Asia/Colombo’,

‘Asia/Damascus’,

‘Asia/Dhaka’,

‘Asia/Dili’,

‘Asia/Dubai’,

‘Asia/Dushanbe’,

‘Asia/Gaza’,

‘Asia/Hebron’,

‘Asia/Ho_Chi_Minh’,

‘Asia/Hong_Kong’,

‘Asia/Hovd’,

‘Asia/Irkutsk’,

‘Asia/Jakarta’,

‘Asia/Jayapura’,

‘Asia/Jerusalem’,

‘Asia/Kabul’,

‘Asia/Kamchatka’,

‘Asia/Karachi’,

‘Asia/Kathmandu’,

‘Asia/Khandyga’,

‘Asia/Kolkata’,

‘Asia/Krasnoyarsk’,

‘Asia/Kuala_Lumpur’,

‘Asia/Kuching’,

‘Asia/Macau’,

‘Asia/Magadan’,

‘Asia/Makassar’,

‘Asia/Manila’,

‘Asia/Nicosia’,

‘Asia/Novokuznetsk’,

‘Asia/Novosibirsk’,

‘Asia/Omsk’,

‘Asia/Oral’,

‘Asia/Pontianak’,

‘Asia/Pyongyang’,

‘Asia/Qatar’,

‘Asia/Qyzylorda’,

‘Asia/Rangoon’,

‘Asia/Riyadh’,

‘Asia/Sakhalin’,

‘Asia/Samarkand’,

‘Asia/Seoul’,

‘Asia/Shanghai’,

‘Asia/Singapore’,

‘Asia/Srednekolymsk’,

‘Asia/Taipei’,

‘Asia/Tashkent’,

‘Asia/Tbilisi’,

‘Asia/Tehran’,

‘Asia/Thimphu’,

‘Asia/Tokyo’,

‘Asia/Tomsk’,

‘Asia/Ulaanbaatar’,

‘Asia/Urumqi’,

‘Asia/Ust-Nera’,

‘Asia/Vladivostok’,

‘Asia/Yakutsk’,

‘Asia/Yekaterinburg’,

‘Asia/Yerevan’,

‘Atlantic/Azores’,

‘Atlantic/Bermuda’,

‘Atlantic/Canary’,

‘Atlantic/Cape_Verde’,

‘Atlantic/Faroe’,

‘Atlantic/Madeira’,

‘Atlantic/Reykjavik’,

‘Atlantic/South_Georgia’,

‘Atlantic/Stanley’,

‘Australia/Adelaide’,

‘Australia/Brisbane’,

‘Australia/Broken_Hill’,

‘Australia/Currie’,

‘Australia/Darwin’,

‘Australia/Eucla’,

‘Australia/Hobart’,

‘Australia/Lindeman’,

‘Australia/Lord_Howe’,

‘Australia/Melbourne’,

‘Australia/Perth’,

‘Australia/Sydney’,

‘GMT’,

‘Europe/Amsterdam’,

‘Europe/Andorra’,

‘Europe/Astrakhan’,

‘Europe/Athens’,

‘Europe/Belgrade’,

‘Europe/Berlin’,

‘Europe/Brussels’,

‘Europe/Bucharest’,

‘Europe/Budapest’,

‘Europe/Chisinau’,

‘Europe/Copenhagen’,

‘Europe/Dublin’,

‘Europe/Gibraltar’,

‘Europe/Helsinki’,

‘Europe/Istanbul’,

‘Europe/Kaliningrad’,

‘Europe/Kiev’,

‘Europe/Kirov’,

‘Europe/Lisbon’,

‘Europe/London’,

‘Europe/Luxembourg’,

‘Europe/Madrid’,

‘Europe/Malta’,

‘Europe/Minsk’,

‘Europe/Monaco’,

‘Europe/Moscow’,

‘Europe/Oslo’,

‘Europe/Paris’,

‘Europe/Prague’,

‘Europe/Riga’,

‘Europe/Rome’,

‘Europe/Samara’,

‘Europe/Simferopol’,

‘Europe/Sofia’,

‘Europe/Stockholm’,

‘Europe/Tallinn’,

‘Europe/Tirane’,

‘Europe/Ulyanovsk’,

‘Europe/Uzhgorod’,

‘Europe/Vienna’,

‘Europe/Vilnius’,

‘Europe/Volgograd’,

‘Europe/Warsaw’,

‘Europe/Zaporozhye’,

‘Europe/Zurich’,

‘Indian/Chagos’,

‘Indian/Christmas’,

‘Indian/Cocos’,

‘Indian/Kerguelen’,

‘Indian/Mahe’,

‘Indian/Maldives’,

‘Indian/Mauritius’,

‘Indian/Reunion’,

‘Pacific/Apia’,

‘Pacific/Auckland’,

‘Pacific/Bougainville’,

‘Pacific/Chatham’,

‘Pacific/Chuuk’,

‘Pacific/Easter’,

‘Pacific/Efate’,

‘Pacific/Enderbury’,

‘Pacific/Fakaofo’,

‘Pacific/Fiji’,

‘Pacific/Funafuti’,

‘Pacific/Galapagos’,

‘Pacific/Gambier’,

‘Pacific/Guadalcanal’,

‘Pacific/Guam’,

‘Pacific/Honolulu’,

‘Pacific/Kiritimati’,

‘Pacific/Kosrae’,

‘Pacific/Kwajalein’,

‘Pacific/Majuro’,

‘Pacific/Marquesas’,

‘Pacific/Nauru’,

‘Pacific/Niue’,

‘Pacific/Norfolk’,

‘Pacific/Noumea’,

‘Pacific/Pago_Pago’,

‘Pacific/Palau’,

‘Pacific/Pitcairn’,

‘Pacific/Pohnpei’,

‘Pacific/Port_Moresby’,

‘Pacific/Rarotonga’,

‘Pacific/Tahiti’,

‘Pacific/Tarawa’,

‘Pacific/Tongatapu’,

‘Pacific/Wake’,

‘Pacific/Wallis’

