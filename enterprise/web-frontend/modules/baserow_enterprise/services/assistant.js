import { createRecordReader } from '@baserow/modules/core/chatRuns/recordReader'

/**
 * The AI Assistant starts from the root URL, not the /api URL like the rest of
 * the Baserow API. This service file therefore overrides the baseURL to be the
 * root URL when making requests to the AI Assistant endpoints.
 */
function getAssistantBaseURL(client) {
  const url = new URL(client.defaults.baseURL)
  return url.origin
}

const cancelledError = () =>
  Object.assign(new Error('Request cancelled'), {
    isAxiosError: true,
    cancelled: true,
  })

export default (client) => {
  return {
    async sendMessage(
      chatUuid,
      message,
      uiContext,
      onDownloadProgress = null,
      options = {}
    ) {
      return await client.post(
        `/assistant/chat/${chatUuid}/messages/`,
        {
          ...(options.runId
            ? { run_id: options.runId, cursor: options.cursor || undefined }
            : { content: message, ui_context: uiContext }),
          ...(options.tabId ? { tab_id: options.tabId } : {}),
        },
        {
          baseURL: getAssistantBaseURL(client),
          adapter: (config) => {
            return new Promise((resolve, reject) => {
              if (options.signal?.aborted) return reject(cancelledError())
              const xhr = new XMLHttpRequest()
              const reader = createRecordReader(
                () => xhr.responseText,
                onDownloadProgress ?? (() => {})
              )

              // Aborting closes only this response; the run keeps going.
              const abort = () => xhr.abort()
              const cleanUp = () =>
                options.signal?.removeEventListener('abort', abort)
              options.signal?.addEventListener('abort', abort, { once: true })

              xhr.open('POST', config.baseURL + config.url, true)
              Object.keys(config.headers).forEach((key) => {
                xhr.setRequestHeader(key, config.headers[key])
              })

              xhr.onprogress = () => {
                reader.read()
              }

              xhr.onload = () => {
                cleanUp()

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
                    errorData = xhr.responseText
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
                cleanUp()
                const error = new Error('Network error occurred')
                error.isAxiosError = true
                reject(error)
              }

              xhr.ontimeout = () => {
                cleanUp()
                const error = new Error('Request timeout')
                error.isAxiosError = true
                reject(error)
              }

              xhr.onabort = () => {
                cleanUp()
                reject(cancelledError())
              }

              xhr.send(config.data)
            })
          },
        }
      )
    },

    async resumeMessage(chatUuid, runId, cursor, onRecord, options = {}) {
      return this.sendMessage(chatUuid, null, null, onRecord, {
        ...options,
        runId,
        cursor,
      })
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
  }
}
