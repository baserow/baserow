<template>
  <div
    class="public-agent-chat"
    :class="{
      [`public-agent-chat--${background}`]: background,
      'public-agent-chat--card': background,
    }"
    :style="pageStyle"
  >
    <div
      v-if="accessChecked"
      class="public-agent-chat__column"
      :class="{ 'public-agent-chat__column--password': showsPassword }"
    >
      <form
        v-if="showsPassword"
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
          class="public-agent-chat__enter"
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
      <template v-else>
        <header v-if="messages.length" class="public-agent-chat__header">
          <h1 class="public-agent-chat__title">{{ info.title }}</h1>
          <Button
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
          <div v-if="!messages.length" class="public-agent-chat__intro">
            <div class="public-agent-chat__mark" aria-hidden="true">
              <i class="baserow-icon-agent"></i>
            </div>
            <h1 v-if="info.title" class="public-agent-chat__intro-title">
              {{ info.title }}
            </h1>
            <ChatMarkdown
              v-if="info.welcome_text"
              class="public-agent-chat__welcome"
              :content="info.welcome_text"
            />
            <ChatSuggestions
              v-if="showSuggestions"
              class="public-agent-chat__suggestions"
              :suggestions="info.suggested_messages"
              @pick="pickSuggestion"
            />
          </div>
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
                <ChatMarkdown
                  v-if="message.content"
                  :content="message.content"
                />
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
          ref="composer"
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
      <div v-if="info.show_powered_by" class="public-agent-chat__powered-by">
        {{ $t('publicAgentChat.poweredBy') }}
        <a
          href="https://baserow.io"
          target="_blank"
          rel="noopener"
          title="Baserow"
        >
          <Logo class="public-agent-chat__powered-by-logo" alt="Baserow" />
        </a>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { createError, useAsyncData, useNuxtApp, useState } from '#app'
import { useHead } from '#imports'

import ChatComposer from '@baserow/modules/core/components/chat/ChatComposer'
import ChatMarkdown from '@baserow/modules/core/components/chat/ChatMarkdown'
import ChatMessage from '@baserow/modules/core/components/chat/ChatMessage'
import ChatSuggestions from '@baserow/modules/core/components/chat/ChatSuggestions'
import ChatTyping from '@baserow/modules/core/components/chat/ChatTyping'
import { readableTextColor } from '@baserow/modules/core/utils/colors'
import { MESSAGE_ROLE } from '@baserow/modules/agent/constants'
import { AGENT_REPLY_STATUS } from '@baserow/modules/agent/utils/replies'
import PublicAgentChatService from '@baserow_enterprise/services/publicAgentChat'
import { usePublicAgentChat } from '@baserow_enterprise/composables/usePublicAgentChat'
import {
  PUBLIC_CHAT_BACKGROUND,
  PUBLIC_CHAT_DEFAULT_FONT,
} from '@baserow_enterprise/composables/useAgentChannels'

definePageMeta({
  middleware: ['settings'],
})

const SEND_ERROR_ID = 'public-agent-chat-send-error'
const NEAR_BOTTOM_PX = 80

const route = useRoute()
const { $i18n, $registry } = useNuxtApp()
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
const composer = ref(null)
const showsPassword = computed(() => needsPassword.value && !unavailable.value)
const background = computed(() => {
  const { background, background_color: color } = info.value
  const drawn =
    background === PUBLIC_CHAT_BACKGROUND.GRADIENT ||
    (background === PUBLIC_CHAT_BACKGROUND.PLAIN && color)
  return drawn ? background : null
})
const fontFamily = computed(() => {
  const type = $registry.exists('fontFamily', info.value.font)
    ? info.value.font
    : PUBLIC_CHAT_DEFAULT_FONT
  const font = $registry.get('fontFamily', type)
  return `"${font.name}",${font.safeFont}`
})
const pageStyle = computed(() => {
  const { accent_color: accent, background_color: color } = info.value
  return {
    fontFamily: fontFamily.value,
    ...(accent && {
      '--chat-accent': accent,
      '--chat-on-accent': readableTextColor(accent),
    }),
    ...(color && { '--public-agent-chat-background-color': color }),
  }
})
const showSuggestions = computed(
  () =>
    Boolean(info.value.suggested_messages?.length) &&
    !unavailable.value &&
    !waiting.value &&
    !sending.value
)

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

async function pickSuggestion(text) {
  draft.value = text
  await nextTick()
  composer.value?.focus()
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
