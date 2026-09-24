export const ERROR_MODEL_DOES_NOT_BELONG_TO_TYPE =
  'ERROR_MODEL_DOES_NOT_BELONG_TO_TYPE'

/**
 * Updates the local AI-field error state when generation reaches the backend
 * with a model that became unavailable before the client received its realtime
 * field update.
 */
export function setAIFieldErrorFromGenerationError(
  store,
  field,
  error,
  localizedMessage
) {
  const response = error?.response?.data
  if (response?.error !== ERROR_MODEL_DOES_NOT_BELONG_TO_TYPE) {
    return false
  }

  store.dispatch('field/setItemError', {
    field,
    value: localizedMessage,
  })
  return true
}
