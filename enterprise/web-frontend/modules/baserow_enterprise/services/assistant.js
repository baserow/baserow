/**
 * The AI Assistant starts from the root URL, not the /api URL like the rest of
 * the Baserow API. This service file therefore overrides the baseURL to be the
 * root URL when making requests to the AI Assistant endpoints.
 */
function getAssistantBaseURL(client) {
  const url = new URL(client.defaults.baseURL)
  return url.origin
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
              let buffer = ''

              // Store XHR for potential cancellation
              activeRequests.set(chatUuid, xhr)

              xhr.open('POST', config.baseURL + config.url, true)
              Object.keys(config.headers).forEach((key) => {
                xhr.setRequestHeader(key, config.headers[key])
              })

              xhr.onprogress = () => {
                const chunk = xhr.responseText.substring(buffer.length)
                buffer = xhr.responseText

                chunk.split('\n\n').forEach(async (line) => {
                  if (line.trim()) {
                    try {
                      await onDownloadProgress(JSON.parse(line))
                    } catch (e) {
                      console.trace(e)
                    }
                  }
                })
              }

              xhr.onload = () => {
                // Clean up stored XHR reference
                activeRequests.delete(chatUuid)

                // Check if the request was successful (2xx status codes)
                if (xhr.status >= 200 && xhr.status < 300) {
                  resolve({ data: xhr.responseText, status: xhr.status })
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
