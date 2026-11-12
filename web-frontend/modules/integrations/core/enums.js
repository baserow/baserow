export const WEBHOOK_EXCLUDE_METHOD_OPTIONS = {
  ALL: false,
  EXCLUDE_GET: true,
}

// The two types behind the HTTP request data source, one returning a single
// record and the other a list of them.
export const HTTP_DATA_SOURCE_TYPE = 'http_get'

export const HTTP_DATA_SOURCE_DEFAULT_TIMEOUT = 10
export const HTTP_DATA_SOURCE_MAX_TIMEOUT = 30

// Matches the backend's `HTTP_DATA_SOURCE_MAX_RESULT_LIMIT`.
export const HTTP_DATA_SOURCE_MAX_RESULT_LIMIT = 100
