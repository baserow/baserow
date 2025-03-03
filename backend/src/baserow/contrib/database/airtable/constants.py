from baserow.contrib.database.fields.utils.duration import (
    H_M,
    H_M_S,
    H_M_S_S,
    H_M_S_SS,
    H_M_S_SSS,
)

AIRTABLE_MAX_DURATION_VALUE = 86399999913600
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
