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
// `www.` prefix or domain-like token) and control characters to prevent abuse of
// transactional emails for phishing.
const URL_LIKE_NAME_REGEX = /https?:\/\/|www\.|\S\.[a-zA-Z]{2,}/i
// eslint-disable-next-line no-control-regex
const CONTROL_CHARS_REGEX = /[\u0000-\u001f\u007f]/

export const nameContainsNoUrl = (value) =>
  !URL_LIKE_NAME_REGEX.test(value) && !CONTROL_CHARS_REGEX.test(value)
