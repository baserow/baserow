export default (client) => {
  return {
    async sendMessage(chatUuid, message, uiContext, onDownloadProgress = null) {
      return await client.post(
        `/ai-assistant/chat/${chatUuid}/messages/`,
        {
          content: message,
          ui_context: uiContext,
        },
        {
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
        `/ai-assistant/chat/?workspace_id=${workspaceId}`
      )
      return data
    },

    async fetchChatMessages(chatUid) {
      const { data } = await client.get(
        `/ai-assistant/chat/${chatUid}/messages/`
      )
      return data
    },
  }
}
