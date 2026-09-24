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

// Decorative letters and digits (circled, negative circled, squared, sub/superscript
// and mathematical alphanumerics). Spammers use them to spell out contact details
// while evading filters, and they never occur in real names. Regional indicators
// (flag emoji) are deliberately excluded from the enclosed alphanumeric supplement.
// Must be kept in sync with `STYLIZED_CHARS_REGEX` in the backend.
const STYLIZED_CHARS_REGEX = new RegExp(
  '[' +
    '\\u2070-\\u209f' + // superscripts and subscripts
    '\\u2460-\\u24ff' + // enclosed alphanumerics
    '\\u2776-\\u2793' + // dingbat circled digits
    '\\u3251-\\u32bf' + // enclosed CJK numbers 21-50
    '\\u{1d400}-\\u{1d7ff}' + // mathematical alphanumeric symbols
    '\\u{1f100}-\\u{1f1e5}' + // enclosed alphanumeric supplement
    ']',
  'u'
)
// Contact IDs (QQ, WhatsApp, phone numbers) embedded in a name to advertise them via
// transactional emails. Short numbers like `Team 2026` or `2025-2026` stay allowed.
const LONG_DIGIT_RUN_REGEX = /\d{6,}/

// NFKC folds lookalike characters (fullwidth, sub/superscript, mathematical
// letters) into their ASCII form, and invisible format characters (zero-width
// spaces, joiners, bidi controls) are stripped because they can be inserted
// between digits or letters to break up a pattern without changing how the name
// renders. They're stripped rather than rejected because zero-width joiners are
// legitimate in emoji sequences and some scripts.
const normalizeName = (value) => value.normalize('NFKC').replace(/\p{Cf}/gu, '')

export const nameContainsNoUrl = (value) =>
  !URL_LIKE_NAME_REGEX.test(normalizeName(value)) &&
  !CONTROL_CHARS_REGEX.test(value)

export const nameContainsNoSpam = (value) =>
  !STYLIZED_CHARS_REGEX.test(value) &&
  !LONG_DIGIT_RUN_REGEX.test(normalizeName(value))

export const nameIsNotEmail = (value) =>
  !EMAIL_LIKE_NAME_REGEX.test(value.trim())
