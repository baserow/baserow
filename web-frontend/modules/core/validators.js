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
