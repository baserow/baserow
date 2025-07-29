import { v4 as uuidv4 } from 'uuid'

export default (client) => {
  return {
    generateConversationUid() {
      return uuidv4()
    },

    async sendMessage(
      chatUid,
      message,
      workspaceId,
      selectedTools = [],
      context = null,
      actionResponse = null,
      onDownloadProgress = null
    ) {
      return await client.post(
        `/ai-assistant/chat/${chatUid}/`,
        {
          message,
          workspace_id: workspaceId,
          selected_tools: selectedTools,
          context,
          action_response: actionResponse,
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
                      console.log(e)
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
      // Note: This endpoint might need to be implemented or use the checkpointer extraction
      const { data } = await client.get(`/ai-assistant/chat/${chatUid}/`)
      return data
    },

    async deleteChat(chatUid) {
      await client.delete(`/ai-assistant/chat/${chatUid}/`)
    },

    async undo(chatUid) {
      await client.post(`/ai-assistant/chat/${chatUid}/undo/`)
    },
  }
}
