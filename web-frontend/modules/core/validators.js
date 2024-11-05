import { maxLength, minLength, required } from '@vuelidate/validators'

export const passwordValidation = {
  required,
  maxLength: maxLength(256),
  minLength: minLength(8),
}
