from baserow.contrib.database.fields.utils.duration import (
    H_M,
    H_M_S,
    H_M_S_S,
    H_M_S_SS,
    H_M_S_SSS,
)

AIRTABLE_MAX_DURATION_VALUE = 86399999913600
AIRTABLE_BASE_URL = "https://airtable.com"
AIRTABLE_API_BASE_URL = f"{AIRTABLE_BASE_URL}/v0.3"
AIRTABLE_EXPORT_JOB_DOWNLOADING_BASE = "downloading-base"
AIRTABLE_EXPORT_JOB_CONVERTING = "converting"
AIRTABLE_EXPORT_JOB_DOWNLOADING_FILES = "downloading-files"
AIRTABLE_BASEROW_COLOR_MAPPING = {
    "blue": "blue",
    "cyan": "light-blue",
    "teal": "light-green",
    "green": "green",
    "yellow": "light-orange",
    "orange": "orange",
    "red": "light-red",
    "pink": "red",
    "purple": "dark-blue",
    "gray": "light-gray",
}
AIRTABLE_NUMBER_FIELD_SEPARATOR_FORMAT_MAPPING = {
    "commaPeriod": "COMMA_PERIOD",
    "periodComma": "PERIOD_COMMA",
    "spaceComma": "SPACE_COMMA",
    "spacePeriod": "SPACE_PERIOD",
}
AIRTABLE_DURATION_FIELD_DURATION_FORMAT_MAPPING = {
    "h:mm": H_M,
    "h:mm:ss": H_M_S,
    "h:mm:ss.s": H_M_S_S,
    "h:mm:ss.ss": H_M_S_SS,
    "h:mm:ss.sss": H_M_S_SSS,
}
# All colors from the rating field in Airtable: yellow, orange, red, pink, purple,
# blue, cyan, teal, green, gray. We're only mapping the ones that we have an
# alternative for.
AIRTABLE_RATING_COLOR_MAPPING = {
    "blue": "dark-blue",
    "green": "dark-green",
    "orange": "dark-orange",
    "red": "dark-red",
}
# All icons from Airtable: star, heart, thumbsUp, flag, dot. We're only mapping the
# ones that we have an alternative for.
AIRTABLE_RATING_ICON_MAPPING = {
    "star": "star",
    "heart": "heart",
    "thumbsUp": "thumbs-up",
    "flag": "flag",
}
AIRTABLE_ASCENDING_MAP = {
    "ascending": True,
    "descending": False,
}
AIRTABLE_DATE_FILTER_VALUE_MAP = {
    "daysAgo": "{timeZone}?{numberOfDays}?nr_days_ago",
    "daysFromNow": "{timeZone}?{numberOfDays}?nr_days_from_now",
    "exactDate": "{timeZone}?{exactDate}?exact_date",
    "nextMonth": "{timeZone}??next_month",
    "nextNumberOfDays": "{timeZone}?{numberOfDays}?nr_days_from_now",
    "nextWeek": "{timeZone}??next_week",
    "oneMonthAgo": "{timeZone}??one_month_ago",
    "oneWeekAgo": "{timeZone}?1?nr_weeks_ago",
    "oneMonthFromNow": "{timeZone}?1?nr_months_from_now",
    "oneWeekFromNow": "{timeZone}?1?nr_weeks_from_now",
    "pastMonth": "{timeZone}?1?nr_months_ago",
    "pastNumberOfDays": "{timeZone}?{numberOfDays}?nr_days_ago",
    "pastWeek": "{timeZone}?1?nr_weeks_ago",
    "pastYear": "{timeZone}?1?nr_years_ago",
    "thisCalendarYear": "{timeZone}?0?nr_years_ago",
    "today": "{timeZone}??today",
    "tomorrow": "{timeZone}??tomorrow",
    "yesterday": "{timeZone}??yesterday",
}
