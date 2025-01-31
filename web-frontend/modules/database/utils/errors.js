/**
 * adapts error various structures into one, common structure
 *
 * @param err
 * @param errorMap
 * @returns {{message: *, content: *, statusCode: (*|number)}}
 */

export const DEFAULT_ERROR_MESSAGE = 'Unknown error'
export const backendErrorMap = {
  500: { title: DEFAULT_ERROR_MESSAGE, message: '' },
}

export function normalizeError(err, errorMap = null) {
  errorMap = errorMap || backendErrorMap

  // axios error - we want response object here
  if (err.response) {
    err = err.response
  }

  const mappedError =
    errorMap[err.data?.error] || errorMap[err.statusCode || err.status]

  // the precedence:
  //  - mapped title
  //  - copy to 1-to-1
  //  - error's data structure
  //  - default error
  const message =
    mappedError?.title ||
    err.message ||
    err.data?.detail ||
    err.data?.error ||
    DEFAULT_ERROR_MESSAGE
  const content =
    mappedError?.message || err.content || err.data?.detail || null

  return {
    message,
    content,
    statusCode: err.statusCode || err.status || 500,
  }
}
