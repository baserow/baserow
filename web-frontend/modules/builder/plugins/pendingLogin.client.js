import { defineNuxtPlugin } from '#app'
import { clearPendingLogin } from '@baserow/modules/builder/utils/pendingLogin'

export default defineNuxtPlugin(() => {
  // Discard failed attempts before auth forms consume provider error parameters,
  // so their pending actions cannot survive into a later login.
  const query = new URLSearchParams(window.location.search)
  if ([...query.keys()].some((key) => /^(saml|oidc)_error__\d+$/.test(key))) {
    clearPendingLogin()
  }
})
