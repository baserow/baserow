// API error codes to silence in Sentry, keyed by HTTP status code.
// These are handled by the application (e.g. forceLogoff) and are not bugs.
export const SILENCED_API_ERRORS = {
  401: ['ERROR_INVALID_ACCESS_TOKEN', 'ERROR_INVALID_REFRESH_TOKEN'],
}

// Browser-extension RPC artifact that rejects a promise when its internal
// object registry can't resolve an id. Not a Baserow error.
export const SILENCED_ERROR_PATTERNS = [
  /Object Not Found Matching Id:\d+, MethodName:\w+, ParamCount:\d+/,
]
