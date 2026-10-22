import axios from 'axios'
import { createRecordReader } from '@baserow/modules/core/chatRuns/recordReader'

/**
 * Reads the body of a failed response, or describes it when it is not a JSON
 * object, such as a proxy's HTML page.
 *
 * @param {XMLHttpRequest} xhr The finished request.
 * @returns {object} The error data.
 */
function parseErrorBody(xhr) {
  let data
  try {
    data = JSON.parse(xhr.responseText)
  } catch {
    data = null
  }
  return data && typeof data === 'object' && !Array.isArray(data)
    ? data
    : { error: 'REQUEST_FAILED', detail: xhr.responseText || xhr.statusText }
}

/**
 * An axios adapter handing each record of a streamed response to `onRecord` as
 * it arrives, so the request keeps the client's headers and interceptors.
 *
 * @param {Function} onRecord Called with each parsed record.
 * @param {AbortSignal} [signal] Aborting closes the response; the run continues.
 * @returns {Function} The axios adapter.
 */
export function createStreamAdapter(onRecord, signal) {
  return (config) =>
    new Promise((resolve, reject) => {
      // Like AxiosError, keep the config so the token refresh interceptor can retry.
      const failure = (message, values = {}) =>
        Object.assign(new Error(message), {
          isAxiosError: true,
          config,
          ...values,
        })
      const cancelled = () => failure('Request cancelled', { cancelled: true })
      if (signal?.aborted) {
        reject(cancelled())
        return
      }
      const xhr = new XMLHttpRequest()
      const reader = createRecordReader(() => xhr.responseText, onRecord)
      const abort = () => xhr.abort()
      const settle = () => signal?.removeEventListener('abort', abort)
      signal?.addEventListener('abort', abort, { once: true })

      xhr.open(config.method.toUpperCase(), axios.getUri(config), true)
      Object.keys(config.headers).forEach((key) => {
        xhr.setRequestHeader(key, config.headers[key])
      })
      const succeeded = () => xhr.status >= 200 && xhr.status < 300
      xhr.onprogress = () => succeeded() && reader.read()
      xhr.onload = () => {
        settle()
        if (succeeded()) {
          reader.flush().then(() =>
            resolve({
              data: '',
              status: xhr.status,
              statusText: xhr.statusText,
              headers: {},
              config,
              request: xhr,
            })
          )
          return
        }
        const data = parseErrorBody(xhr)
        reject(
          failure(data.detail || xhr.statusText, {
            response: { data, status: xhr.status, statusText: xhr.statusText },
          })
        )
      }
      xhr.onerror = () => {
        settle()
        reject(failure('Network error occurred'))
      }
      xhr.onabort = () => {
        settle()
        reject(cancelled())
      }
      xhr.send()
    })
}
