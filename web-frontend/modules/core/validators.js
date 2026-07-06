/*
  In case the password validation rules change the PasswordInput component
  needs to be updated as well in order to display possible new error messages

  modules/core/components/helpers/PasswordInput.vue
*/

import { maxLength, minLength, required } from '@vuelidate/validators'

export const passwordValidation = {
  required,
  maxLength: maxLength(256),
  minLength: minLength(8),
}

// Must be kept in sync with the backend equivalent in
// backend/src/baserow/api/user/validators.py. Rejects URL-like content (protocol,
// `www.` prefix, domain-like token with a high risk TLD, or any domain-like token
// followed by a path), control characters, and email addresses to prevent abuse of
// transactional emails for phishing. Startup TLDs like `.ai` are deliberately not
// listed because real users have names like `startup.ai`.
const HIGH_RISK_TLDS =
  'com|net|org|io|co|info|biz|xyz|top|shop|site|online|link|club|app|dev|' +
  'live|me|ly|to|cc|gd|ru|cn|de|uk|nl|tk|ml|ga|cf|gq|click|icu|buzz|pw|vip'
const URL_LIKE_NAME_REGEX = new RegExp(
  `https?://|www\\.|[a-z0-9][a-z0-9-]*\\.(?:${HIGH_RISK_TLDS})\\b|\\S\\.[a-zA-Z]{2,}/`,
  'i'
)
const EMAIL_LIKE_NAME_REGEX = /^[^@\s]+@[^@\s]+\.[^@\s]+$/
// eslint-disable-next-line no-control-regex
const CONTROL_CHARS_REGEX = /[\u0000-\u001f\u007f]/

export const nameContainsNoUrl = (value) =>
  !URL_LIKE_NAME_REGEX.test(value) && !CONTROL_CHARS_REGEX.test(value)

export const nameIsNotEmail = (value) =>
  !EMAIL_LIKE_NAME_REGEX.test(value.trim())
