export const IMAGE_FILE_TYPES = [
  'image/jpeg',
  'image/jpg',
  'image/png',
  'image/apng',
  'image/gif',
  'image/tiff',
  'image/bmp',
  'image/webp',
]

export const FAVICON_IMAGE_FILE_TYPES = [...IMAGE_FILE_TYPES, 'image/x-icon']

// Keep these in sync with the backend options in
// baserow.core.models.Settings.EmailVerificationOptions
export const EMAIL_VERIFICATION_OPTIONS = {
  NO_VERIFICATION: 'no_verification',
  RECOMMENDED: 'recommended',
  ENFORCED: 'enforced',
}

// Keep these in sync with the backend options in
// baserow.core.models.UserProfile.EmailNotificationFrequencyOptions
export const EMAIL_NOTIFICATIONS_FREQUENCY_OPTIONS = {
  INSTANT: 'instant',
  DAILY: 'daily',
  WEEKLY: 'weekly',
  NEVER: 'never',
}

export const DATA_TYPE_TO_ICON_MAP = {
  string: 'iconoir-text',
  number: 'baserow-icon-hashtag',
  integer: 'baserow-icon-hashtag',
  boolean: 'baserow-icon-circle-checked',
  date: 'iconoir-calendar',
  datetime: 'iconoir-calendar',
  array: 'iconoir-list',
  file: 'iconoir-attachment',
  union: 'iconoir-union-alt',
}

export const UNKNOWN_DATA_TYPE_ICON = 'iconoir-question-mark'

export const RATING_STYLES = {
  STAR: 'star',
  HEART: 'heart',
  THUMBS_UP: 'thumbs-up',
  FLAG: 'flag',
  SMILE: 'smile',
}

export const FORMULA_TYPE = {
  FUNCTION: 'function',
  OPERATOR: 'operator',
}

export const FORMULA_CATEGORY = {
  TEXT: {
    category: 'categoryText',
    iconClass: 'baserow-icon-text',
  },
  NUMBER: {
    category: 'categoryNumber',
    iconClass: 'baserow-icon-hashtag',
  },
  BOOLEAN: {
    category: 'categoryBoolean',
    iconClass: 'baserow-icon-circle-checked',
  },
  DATE: {
    category: 'categoryDate',
    iconClass: 'iconoir-calendar',
  },
  FILE: {
    category: 'categoryFile',
    iconClass: 'baserow-icon-file',
  },
  CONDITION: {
    category: 'categoryCondition',
    iconClass: 'iconoir-code-brackets-square',
  },
}
