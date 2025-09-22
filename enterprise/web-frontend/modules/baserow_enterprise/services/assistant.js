/**
 * The AI Assistant starts from the root URL, not the /api URL like the rest of
 * the Baserow API. This service file therefore overrides the baseURL to be the
 * root URL when making requests to the AI Assistant endpoints.
 */
function getAssistantBaseURL(client) {
  return client.defaults.baseURL.split('/api')[0]
}

export default (client) => {
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

              xhr.onload = () =>
                resolve({ data: xhr.responseText, status: xhr.status })
              xhr.onerror = reject
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
  }
}
