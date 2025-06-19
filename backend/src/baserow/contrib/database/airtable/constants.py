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
    "blue": "light-blue",
    "cyan": "light-cyan",
    "teal": "light-pink",  # Baserow doesn't have teal, so we're using the left-over color
    "green": "light-green",
    "yellow": "light-yellow",
    "orange": "light-orange",
    "red": "light-red",
    "purple": "light-purple",
    "gray": "light-gray",
    "blueMedium": "blue",
    "cyanMedium": "cyan",
    "tealMedium": "pink",
    "greenMedium": "green",
    "yellowMedium": "yellow",
    "orangeMedium": "orange",
    "redMedium": "red",
    "purpleMedium": "purple",
    "grayMedium": "gray",
    "blueDark": "dark-blue",
    "cyanDark": "dark-cyan",
    "tealDark": "dark-pink",
    "greenDark": "dark-green",
    "yellowDark": "dark-yellow",
    "orangeDark": "dark-orange",
    "redDark": "dark-red",
    "purpleDark": "dark-purple",
    "grayDark": "dark-gray",
    "blueDarker": "darker-blue",
    "cyanDarker": "darker-cyan",
    "tealDarker": "darker-pink",
    "greenDarker": "darker-green",
    "yellowDarker": "darker-yellow",
    "orangeDarker": "darker-orange",
    "redDarker": "darker-red",
    "purpleDarker": "darker-purple",
    "grayDarker": "darker-gray",
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
    "nextYear": "{timeZone}??next_year",
    "oneMonthAgo": "{timeZone}??one_month_ago",
    "oneWeekAgo": "{timeZone}?1?nr_weeks_ago",
    "oneMonthFromNow": "{timeZone}?1?nr_months_from_now",
    "oneWeekFromNow": "{timeZone}?1?nr_weeks_from_now",
    "pastMonth": "{timeZone}?1?nr_months_ago",
    "pastNumberOfDays": "{timeZone}?{numberOfDays}?nr_days_ago",
    "pastWeek": "{timeZone}?1?nr_weeks_ago",
    "pastYear": "{timeZone}?1?nr_years_ago",
    "thisCalendarYear": "{timeZone}??this_year",
    "thisCalendarMonth": "{timeZone}??this_month",
    "thisCalendarWeek": "{timeZone}??this_week",
    "today": "{timeZone}??today",
    "tomorrow": "{timeZone}??tomorrow",
    "yesterday": "{timeZone}??yesterday",
}
AIRTABLE_GALLERY_VIEW_COVER_CROP_TYPE = "crop"

AIRTABLE_DOWNLOAD_FILE_TYPE_FETCH = "fetch"
AIRTABLE_DOWNLOAD_FILE_TYPE_ATTACHMENT_ENDPOINT = "attachment_endpoint"
