export const ERROR_MODEL_DOES_NOT_BELONG_TO_TYPE =
  'ERROR_MODEL_DOES_NOT_BELONG_TO_TYPE'

const MODEL_NOT_AVAILABLE_MESSAGE =
  'The selected AI model is disabled or no longer available.'

/**
 * Updates the local AI-field error state when generation reaches the backend
 * with a model that became unavailable before the client received its realtime
 * field update.
 */
export function setAIFieldErrorFromGenerationError(store, field, error) {
  const response = error?.response?.data
  if (response?.error !== ERROR_MODEL_DOES_NOT_BELONG_TO_TYPE) {
    return false
  }

  const detail =
    typeof response.detail === 'string'
      ? response.detail
      : MODEL_NOT_AVAILABLE_MESSAGE
  store.dispatch('field/setItemError', { field, value: detail })
  return true
}
