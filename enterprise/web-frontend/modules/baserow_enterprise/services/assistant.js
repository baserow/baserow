// json.dumps escapes newlines, so this can never occur inside a record.
const RECORD_DELIMITER = '\n\n'

const STREAM_LOG_PREFIX = '[assistant stream]'
const CORRUPT_RECORD_PREVIEW_LENGTH = 200

/**
 * The AI Assistant starts from the root URL, not the /api URL like the rest of
 * the Baserow API. This service file therefore overrides the baseURL to be the
 * root URL when making requests to the AI Assistant endpoints.
 */
function getAssistantBaseURL(client) {
  const url = new URL(client.defaults.baseURL)
  return url.origin
}

/**
 * Turns the cumulative `xhr.responseText` into whole delimiter-terminated
 * records and hands them to the consumer one at a time, in arrival order.
 *
 * @param {Function} readResponseText Returns everything received so far.
 * @param {Function} onRecord Called with each parsed record, may be async.
 * @returns {{read: Function, flush: Function}} Reader driven by the XHR events.
 */
function createRecordReader(readResponseText, onRecord) {
  let consumed = 0
  let pending = ''
  let dispatched = Promise.resolve()

  // Taking records synchronously keeps the buffer consistent across progress events.
  const take = (isFinal) => {
    const responseText = readResponseText()
    pending += responseText.substring(consumed)
    consumed = responseText.length

    const records = pending.split(RECORD_DELIMITER)
    pending = isFinal ? '' : records.pop()
    return records.filter((record) => record.trim() !== '')
  }

  const dispatch = (records) => {
    dispatched = dispatched.then(async () => {
      for (const record of records) {
        let update
        try {
          update = JSON.parse(record)
        } catch (error) {
          console.error(`${STREAM_LOG_PREFIX} dropped an unparsable record`, {
            length: record.length,
            preview: record.slice(0, CORRUPT_RECORD_PREVIEW_LENGTH),
            error,
          })
          continue
        }
        try {
          await onRecord(update)
        } catch (error) {
          console.error(`${STREAM_LOG_PREFIX} record handler failed`, error)
        }
      }
    })
    return dispatched
  }

  return {
    read: () => dispatch(take(false)),
    flush: () => dispatch(take(true)),
  }
}

export default (client) => {
  // Store active XHR request by chat UUID for cancellation
  const activeRequests = new Map()

  return {
    async sendMessage(chatUuid, message, uiContext, onDownloadProgress = null) {
      return await client.post(
        `/assistant/chat/${chatUuid}/messages/`,
        {
          content: message,
          ui_context: uiContext,
        },
        {
          baseURL: getAssistantBaseURL(client),
          adapter: (config) => {
            return new Promise((resolve, reject) => {
              const xhr = new XMLHttpRequest()
              const reader = createRecordReader(
                () => xhr.responseText,
                onDownloadProgress ?? (() => {})
              )

              // Store XHR for potential cancellation
              activeRequests.set(chatUuid, xhr)

              xhr.open('POST', config.baseURL + config.url, true)
              Object.keys(config.headers).forEach((key) => {
                xhr.setRequestHeader(key, config.headers[key])
              })

              xhr.onprogress = () => {
                reader.read()
              }

              xhr.onload = () => {
                // Clean up stored XHR reference
                activeRequests.delete(chatUuid)

                // Check if the request was successful (2xx status codes)
                if (xhr.status >= 200 && xhr.status < 300) {
                  reader.flush().then(() => {
                    resolve({ data: xhr.responseText, status: xhr.status })
                  })
                } else {
                  let errorData
                  try {
                    errorData = JSON.parse(xhr.responseText)
                  } catch {
                    errorData = {
                      error: 'REQUEST_FAILED',
                      detail: xhr.responseText || xhr.statusText,
                    }
                  }

                  const error = new Error(
                    errorData.detail ||
                      errorData.message ||
                      `Oops! Something went wrong. Please try again.`
                  )
                  error.response = {
                    data: errorData,
                    status: xhr.status,
                    statusText: xhr.statusText,
                  }
                  error.isAxiosError = true

                  reject(error)
                }
              }

              xhr.onerror = () => {
                // Clean up stored XHR reference
                activeRequests.delete(chatUuid)
                const error = new Error('Network error occurred')
                error.isAxiosError = true
                reject(error)
              }

              xhr.ontimeout = () => {
                // Clean up stored XHR reference
                activeRequests.delete(chatUuid)
                const error = new Error('Request timeout')
                error.isAxiosError = true
                reject(error)
              }

              xhr.onabort = () => {
                // Clean up stored XHR reference
                activeRequests.delete(chatUuid)
                const error = new Error('Request cancelled')
                error.isAxiosError = true
                error.cancelled = true
                reject(error)
              }

              xhr.send(config.data)
            })
          },
        }
      )
    },

    async fetchChats(workspaceId) {
      const { data } = await client.get(
        `/assistant/chat/?workspace_id=${workspaceId}`,
        {
          baseURL: getAssistantBaseURL(client),
        }
      )
      return data
    },

    async fetchChatMessages(chatUid) {
      const { data } = await client.get(
        `/assistant/chat/${chatUid}/messages/`,
        {
          baseURL: getAssistantBaseURL(client),
        }
      )
      return data
    },

    async submitFeedback(messageId, sentiment, feedback) {
      const { data } = await client.put(
        `/assistant/messages/${messageId}/feedback/`,
        { sentiment, feedback },
        {
          baseURL: getAssistantBaseURL(client),
        }
      )
      return data
    },

    async fetchOnboardingPromptSuggestions({ industry, team, language }) {
      const { data } = await client.post(
        '/assistant/onboarding/prompt-suggestions/',
        {
          industry,
          team,
          language,
        },
        {
          baseURL: getAssistantBaseURL(client),
        }
      )
      return data.suggestions
    },

    async cancelMessage(chatUuid) {
      await client.delete(`/assistant/chat/${chatUuid}/cancel/`, {
        baseURL: getAssistantBaseURL(client),
      })

      // Abort the XHR request if it exists
      const xhr = activeRequests.get(chatUuid)
      if (xhr) {
        // Optionally, set a custom property to indicate user-initiated abort
        xhr._userCancelled = true
        xhr.abort()
      }
    },
  }
}
