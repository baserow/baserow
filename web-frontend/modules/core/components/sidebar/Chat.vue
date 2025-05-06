<template>
  <div class="chat-container">
    <div class="messages">
      <div v-for="(msg, i) in messages" :key="i" :class="msg.role">
        <strong>{{ msg.role === 'user' ? 'You' : 'ChatGPT' }}:</strong>
        <pre>{{ msg.content }}</pre>
      </div>
      <div v-if="streamingMessage" class="assistant">
        <strong>ChatGPT:</strong>
        <pre>{{ streamingMessage }}</pre>
      </div>
    </div>
    <div class="input">
      <input
        v-model="input"
        class="input-input"
        :disabled="loading"
        placeholder="Your message..."
        @keyup.enter="sendMessage"
      />
      <button :disabled="loading" @click="sendMessage">Send</button>
    </div>
  </div>
</template>

<script>
export default {
  props: {
    initialMessages: {
      type: Array,
      default: () => [],
    },
    apiKey: {
      type: String,
      required: true,
    },
    tools: {
      type: Array,
      default: () => [],
    },
    toolHandlers: {
      type: Object,
      default: () => ({}),
    },
  },
  data() {
    return {
      input: '',
      messages: [],
      streamingMessage: '',
      loading: false,
    }
  },
  methods: {
    async sendMessage() {
      if (!this.input.trim()) return

      this.loading = true
      const userMessage = { role: 'user', content: this.input }
      this.messages.push(userMessage)
      this.input = ''
      this.streamingMessage = ''

      const payload = {
        model: 'gpt-4',
        messages: [...this.initialMessages, ...this.messages],
        stream: true,
        ...(this.tools.length > 0 && { tools: this.tools }),
      }

      try {
        const response = await fetch(
          'https://api.openai.com/v1/chat/completions',
          {
            method: 'POST',
            headers: {
              Authorization: `Bearer ${this.apiKey}`,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
          }
        )

        if (!response.ok) throw new Error('API response error')

        const reader = response.body.getReader()
        const decoder = new TextDecoder('utf-8')
        let fullMessage = ''
        const toolCallFragments = {}

        while (true) {
          const { value, done } = await reader.read()
          if (done) break

          const chunk = decoder.decode(value)
          const lines = chunk
            .split('\n')
            .filter((line) => line.trim().startsWith('data: '))

          for (const line of lines) {
            const jsonStr = line.replace('data: ', '').trim()
            if (jsonStr === '[DONE]') continue

            try {
              const json = JSON.parse(jsonStr)
              const choice = json.choices[0]
              const delta = choice.delta

              if (delta?.content) {
                fullMessage += delta.content
                this.streamingMessage = fullMessage
              }

              if (delta?.tool_calls) {
                for (const call of delta.tool_calls) {
                  const id = call.id

                  if (!toolCallFragments[id]) {
                    toolCallFragments[id] = {
                      id,
                      type: call.type,
                      function: { name: '', arguments: '' },
                    }
                  }

                  // accumulation par morceau
                  if (call.function?.name) {
                    toolCallFragments[id].function.name += call.function.name
                  }

                  if (call.function?.arguments) {
                    toolCallFragments[id].function.arguments +=
                      call.function.arguments
                  }
                }
              }
            } catch (e) {
              console.error('JSON parse error', e)
            }
          }
        }

        console.log(toolCallFragments)
        const toolCalls = Object.values(toolCallFragments)

        if (toolCalls.length) {
          console.log(toolCalls)
          const functionCall = toolCalls[0]
          const toolName = functionCall.function.name
          let args = {}

          try {
            args = JSON.parse(functionCall.function.arguments || '{}')
          } catch (e) {
            console.error('Failed to parse tool arguments', e)
          }

          if (this.toolHandlers[toolName]) {
            try {
              const result = await this.toolHandlers[toolName](args)
              const toolMessage = {
                role: 'tool',
                tool_call_id: functionCall.id,
                content: result,
              }
              this.messages.push(
                userMessage,
                { role: 'assistant', tool_calls: [functionCall] },
                toolMessage
              )
              this.sendMessage()
              return
            } catch (toolError) {
              console.error('Tool execution error', toolError)
              this.messages.push({
                role: 'assistant',
                content: 'Tool execution failed.',
              })
            }
          } else {
            this.messages.push({
              role: 'assistant',
              content: `Unknown tool: ${toolName}`,
            })
          }
        } else {
          this.messages.push({ role: 'assistant', content: fullMessage })
        }

        this.streamingMessage = ''
      } catch (err) {
        console.error(err)
        this.messages.push({
          role: 'assistant',
          content: 'Error communicating with the API.',
        })
        this.streamingMessage = ''
      } finally {
        this.loading = false
      }
    },
  },
}
</script>

<style scoped>
.chat-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  flex: 1;
}
.messages {
  border: 1px solid #ccc;
  padding: 1em;
  height: 100%;
  overflow-y: auto;
  margin-bottom: 1em;
  flex: 1;
}
.user {
  text-align: right;
}
.assistant {
  text-align: left;
}
.input {
  display: flex;
}
.input-input {
  flex: 1;
  padding: 0.5em;
}
button {
  padding: 0.5em 1em;
}
</style>
