<template>
  <div class="public-agent-chat">
    <form
      v-if="needsPassword && !unavailable"
      class="public-agent-chat__password"
      @submit.prevent="submitPassword"
    >
      <h1 class="public-agent-chat__password-title">
        {{ $t('publicAgentChat.passwordTitle') }}
      </h1>
      <p class="public-agent-chat__password-description">
        {{ $t('publicAgentChat.passwordDescription') }}
      </p>
      <FormGroup
        small-label
        :label="$t('field.password')"
        :error="passwordError || authorizeFailed"
        class="margin-bottom-2"
      >
        <FormInput
          v-model="password"
          type="password"
          size="large"
          autocomplete="current-password"
          :error="passwordError || authorizeFailed"
        />
        <template #error>{{
          passwordError
            ? $t('publicAgentChat.wrongPassword')
            : $t('publicAgentChat.failed')
        }}</template>
      </FormGroup>
      <Button
        type="primary"
        size="large"
        button-type="submit"
        full-width
        :loading="authorizing"
        :disabled="authorizing || !password"
      >
        {{ $t('publicAgentChat.enter') }}
      </Button>
    </form>
    <template v-else-if="accessChecked">
      <header class="public-agent-chat__header">
        <h1 class="public-agent-chat__title">{{ info.title }}</h1>
        <Button
          v-if="messages.length"
          type="secondary"
          size="small"
          button-type="button"
          :disabled="sending"
          @click="reset"
        >
          {{ $t('publicAgentChat.newConversation') }}
        </Button>
      </header>
      <div ref="messagesElement" class="public-agent-chat__messages">
        <RichTextEditor
          v-if="!messages.length && info.welcome_text"
          class="public-agent-chat__welcome"
          :model-value="info.welcome_text"
          :editable="false"
          :enable-rich-text-formatting="true"
        />
        <template v-for="message in messages" :key="message.id">
          <ChatMessage v-if="message.role !== MESSAGE_ROLE.ASSISTANT" own>
            <div class="chat-message__bubble">{{ message.content }}</div>
          </ChatMessage>
          <ChatMessage
            v-else-if="
              showsReply(message) || isFailed(message) || isStopped(message)
            "
          >
            <div
              v-if="showsReply(message)"
              class="chat-message__bubble"
              aria-live="polite"
              :aria-busy="isRunning(message)"
            >
              <ChatMarkdown v-if="message.content" :content="message.content" />
              <ChatTyping v-else />
            </div>
            <div
              v-if="isFailed(message)"
              class="chat-message__bubble chat-message__bubble--error"
            >
              {{ $t('publicAgentChat.failed') }}
            </div>
            <div v-if="isStopped(message)" class="chat-message__bubble">
              {{ $t('publicAgentChat.stopped') }}
            </div>
          </ChatMessage>
        </template>
      </div>
      <p
        v-if="restoreFailed && !unavailable"
        class="public-agent-chat__restore-failed"
        role="status"
      >
        {{ $t('publicAgentChat.restoreFailed') }}
      </p>
      <p v-if="unavailable" class="public-agent-chat__unavailable">
        {{ $t('publicAgentChat.unavailable') }}
      </p>
      <ChatComposer
        v-else
        v-model="draft"
        class="public-agent-chat__composer"
        :placeholder="$t('publicAgentChat.messagePlaceholder')"
        :readonly="sending"
        :disabled="waiting"
        :described-by="sendError ? SEND_ERROR_ID : undefined"
        :maxlength="100000"
        :can-send="Boolean(draft.trim())"
        :sending="sending"
        :running="replying"
        :activity="waiting ? $t('publicAgentChat.waiting') : ''"
        :activity-tone="waiting ? 'waiting' : 'default'"
        :error="sendError ? $t('publicAgentChat.failed') : ''"
        :error-id="SEND_ERROR_ID"
        :send-label="$t('agent.send')"
        :stop-label="$t('agent.stop')"
        @send="sendDraft"
        @stop="stop"
      />
    </template>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { createError, useAsyncData, useNuxtApp, useState } from '#app'
import { useHead } from '#imports'

import ChatComposer from '@baserow/modules/core/components/chat/ChatComposer'
import ChatMarkdown from '@baserow/modules/core/components/chat/ChatMarkdown'
import ChatMessage from '@baserow/modules/core/components/chat/ChatMessage'
import ChatTyping from '@baserow/modules/core/components/chat/ChatTyping'
import RichTextEditor from '@baserow/modules/core/components/editor/RichTextEditor'
import { MESSAGE_ROLE } from '@baserow/modules/agent/constants'
import { AGENT_REPLY_STATUS } from '@baserow/modules/agent/utils/replies'
import PublicAgentChatService from '@baserow_enterprise/services/publicAgentChat'
import { usePublicAgentChat } from '@baserow_enterprise/composables/usePublicAgentChat'

definePageMeta({
  middleware: ['settings'],
})

const SEND_ERROR_ID = 'public-agent-chat-send-error'
const NEAR_BOTTOM_PX = 80

const route = useRoute()
const { $i18n } = useNuxtApp()
const slug = route.params.slug

const originalLocale = ref($i18n.locale.value)
const detectedLocale = useState('public-agent-chat-detected-locale', () => {
  return $i18n.getBrowserLocale() || $i18n.defaultLocale
})
$i18n.locale.value = detectedLocale.value
await $i18n.loadLocaleMessages(detectedLocale.value)

const { data, error } = await useAsyncData(
  `agent-public-chat-${slug}`,
  async () => {
    const { $client } = useNuxtApp()
    try {
      const { data } = await PublicAgentChatService($client).getInfo(slug)
      return data
    } catch (e) {
      const statusCode = e.response?.status
      if (statusCode === 404) {
        throw createError({
          statusCode: 404,
          message: 'Chat not found.',
          data: { report: false },
          fatal: true,
        })
      }
      throw createError({
        statusCode: statusCode || 500,
        message: e.message || 'Error loading the chat.',
        fatal: true,
      })
    }
  }
)

if (error.value) {
  throw error.value
}

const {
  info,
  accessChecked,
  needsPassword,
  passwordError,
  messages,
  replying,
  waiting,
  sending,
  sendError,
  unavailable,
  restoreFailed,
  authorize,
  send,
  stop,
  reset,
} = usePublicAgentChat(slug, data.value)

useHead(() => ({
  title: info.value.title || $i18n.t('publicAgentChat.passwordTitle'),
}))

const password = ref('')
const authorizing = ref(false)
const authorizeFailed = ref(false)
const draft = ref('')
const messagesElement = ref(null)

const isRunning = (message) =>
  [AGENT_REPLY_STATUS.QUEUED, AGENT_REPLY_STATUS.RUNNING].includes(
    message.status
  )
const isFailed = (message) => message.status === AGENT_REPLY_STATUS.FAILED
const isStopped = (message) =>
  message.status === AGENT_REPLY_STATUS.CANCELLED && !message.content
const showsReply = (message) => Boolean(message.content) || isRunning(message)

async function submitPassword() {
  authorizing.value = true
  authorizeFailed.value = false
  try {
    await authorize(password.value)
  } catch {
    authorizeFailed.value = true
  } finally {
    authorizing.value = false
  }
}

async function sendDraft() {
  if (await send(draft.value)) draft.value = ''
}

watch(messages, async () => {
  const element = messagesElement.value
  if (!element) return
  const nearBottom =
    element.scrollHeight - element.scrollTop - element.clientHeight <
    NEAR_BOTTOM_PX
  await nextTick()
  if (nearBottom) element.scrollTop = element.scrollHeight
})

onBeforeUnmount(() => {
  $i18n.locale.value = originalLocale.value
})
</script>
