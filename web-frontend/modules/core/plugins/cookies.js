import { initCookiesInstance } from '@baserow/modules/core/utils/cookies'

/**
 * Initialize the cookie instance to make sure it's available for other calls
 */
export default function ({ req }) {
  initCookiesInstance(process.server ? req : null)
}
