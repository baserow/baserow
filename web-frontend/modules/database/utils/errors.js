/**
 * Returns most expected error structure.
 *
 * When an error is thrown, it can be of any type. This function tries to return
 * the most useful error data from the error. It tries to return any first of the
 * following:
 *
 * * http response body, if it's a DRF error structure
 * * http response object
 * * the error as-is in any other case
 *
 * @param err
 * @param errorMap
 * @returns {*}
 */
export function normalizeError(err) {
  err = err.response?.data?.message ? err.response.data : err.response || err
  return {
    message: err.message,
    content: err.detail,
    statusCode: err.statusCode,
  }
}
