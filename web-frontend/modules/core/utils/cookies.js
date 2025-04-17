import Cookies from 'universal-cookie'

let globalCookiesInstance = null

/**
 * Get or create the global cookies instance
 * @param {Object} headers - Optional headers for cookie initialization
 * @returns {Cookies} The global cookies instance
 */
export const getCookiesInstance = (headers) => {
  if (!globalCookiesInstance) {
    globalCookiesInstance = new Cookies(headers)
  }
  return globalCookiesInstance
}
