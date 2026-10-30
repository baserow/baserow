import { required, maxLength, helpers } from '@vuelidate/validators'

const isValidName = (name) => {
  if (name[0] === '-' || name[0] === '_') {
    return false
  }
  return /^[a-zA-Z0-9-_.]+$/.test(name)
}

/**
 * The rules of the rows of an HTTP request's headers or query params, for the
 * list showing them and for a form which has to check them while the list
 * isn't shown.
 *
 * @param {Function} t translates the error messages.
 */
export const httpKeyValueRowsRules = (t) => ({
  $each: helpers.forEach({
    key: {
      required: helpers.withMessage(
        t('coreHTTPRequestServiceForm.nameFieldRequired'),
        required
      ),
      invalid: helpers.withMessage(
        t('coreHTTPRequestServiceForm.nameFieldInvalid'),
        isValidName
      ),
      maxLength: helpers.withMessage(
        t('error.maxLength', { max: 255 }),
        maxLength(225)
      ),
    },
    value: {},
  }),
})
