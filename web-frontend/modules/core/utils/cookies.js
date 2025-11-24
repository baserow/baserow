import Cookies from 'universal-cookie'

let globalCookiesInstance = null

/**
 * Initialized the cookie handler.
 * @param {Object} headers - Optional headers for cookie initialization
 * @returns {Cookies} The global cookies instance
 */
export const initCookiesInstance = (req) => {
  globalCookiesInstance = new Cookies(req?.headers?.cookie)
  return globalCookiesInstance
}

/**
 * Get the global cookies instance
 * @returns {Cookies} The global cookies instance
 */
export const getCookiesInstance = () => {
  if (!globalCookiesInstance) {
    throw new Error('Cookies used before initialization')
  }
  return globalCookiesInstance
}
