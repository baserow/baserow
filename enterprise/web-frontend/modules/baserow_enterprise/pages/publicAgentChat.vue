<template>
  <div class="public-agent-chat">
    <Toasts></Toasts>
    <header class="public-agent-chat__header">
      <span class="public-agent-chat__avatar">
        <i class="baserow-icon-agent"></i>
      </span>
      <span class="public-agent-chat__title">{{ info.title }}</span>
      <Button
        v-if="messages.length > 0"
        tag="a"
        type="secondary"
        icon="iconoir-plus"
        class="public-agent-chat__restart"
        :title="$t('publicAgentChat.newConversation')"
        @click="restart"
      >
        {{ $t('publicAgentChat.newConversation') }}
      </Button>
    </header>
    <main
      ref="scroller"
      class="agent-chat__messages public-agent-chat__messages"
      :class="{ 'agent-chat__messages--welcome': messages.length === 0 }"
    >
      <div class="agent-chat__column">
        <div v-if="messages.length === 0" class="agent-chat-welcome">
          <div class="agent-chat-welcome__icon">
            <i class="baserow-icon-agent"></i>
          </div>
          <h2 class="agent-chat-welcome__title">
            <strong class="agent-chat-welcome__title-name">{{
              info.title
            }}</strong>
          </h2>
          <p
            v-if="info.welcome_text"
            class="agent-chat-welcome__subtitle public-agent-chat__welcome-text"
          >
            {{ info.welcome_text }}
          </p>
        </div>
        <template v-for="message in messages" :key="message.key">
          <div
            v-if="message.role === 'human'"
            class="agent-chat-message agent-chat-message--human"
          >
            <div class="agent-chat-message__content">{{ message.content }}</div>
          </div>
          <div v-else class="agent-chat-message agent-chat-message--ai">
            <!-- eslint-disable vue/no-v-html -->
            <div
              class="agent-chat-message__content"
              v-html="render(message.content)"
            ></div>
            <!-- eslint-enable vue/no-v-html -->
          </div>
        </template>
        <div v-if="partial" class="agent-chat-message agent-chat-message--ai">
          <!-- eslint-disable vue/no-v-html -->
          <div
            class="agent-chat-message__content"
            v-html="render(partial)"
          ></div>
          <!-- eslint-enable vue/no-v-html -->
        </div>
        <div
          v-else-if="status === 'working'"
          class="agent-chat-reasoning agent-chat-reasoning--live public-agent-chat__working"
        >
          <span class="agent-chat-reasoning__indicator"></span>
          <span>{{ $t('publicAgentChat.working') }}</span>
        </div>
        <div
          v-if="status === 'error'"
          class="agent-chat-message agent-chat-message--error"
        >
          {{ $t('publicAgentChat.error') }}
        </div>
      </div>
    </main>
    <footer class="agent-chat__composer public-agent-chat__footer">
      <div class="agent-chat__column">
        <div
          v-if="composerStatus"
          class="agent-chat__composer-status"
          :class="{
            'agent-chat__composer-status--running': status === 'working',
            'agent-chat__composer-status--awaiting':
              status === 'waiting_for_approval',
          }"
        >
          <i
            class="agent-chat__composer-status-icon"
            :class="
              status === 'waiting_for_approval'
                ? 'iconoir-shield-check'
                : 'iconoir-sparks'
            "
          ></i>
          <span class="agent-chat__composer-status-message">
            {{ composerStatus }}
          </span>
        </div>
        <form
          class="agent-chat__composer-box"
          :class="{ 'agent-chat__composer-box--after-status': composerStatus }"
          @submit.prevent="send"
        >
          <textarea
            ref="input"
            v-model="draft"
            class="agent-chat__composer-textarea public-agent-chat__textarea"
            rows="1"
            :placeholder="$t('publicAgentChat.placeholder')"
            :disabled="busy"
            @input="resize"
            @keydown.enter.exact.prevent="send"
          ></textarea>
          <div class="agent-chat__composer-row public-agent-chat__composer-row">
            <button
              type="submit"
              class="agent-chat__send-button"
              :class="{ 'agent-chat__send-button--disabled': !canSend }"
              :disabled="!canSend"
              :title="$t('publicAgentChat.send')"
            >
              <i class="iconoir-arrow-up"></i>
            </button>
          </div>
        </form>
        <div class="public-agent-chat__powered">
          <span>{{ $t('publicAgentChat.poweredBy') }}</span>
          <ExternalLinkBaserowLogo class="public-agent-chat__logo" />
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  createError,
  navigateTo,
  useAsyncData,
  useHead,
  useI18n,
  useNuxtApp,
  useState,
} from '#imports'
import Toasts from '@baserow/modules/core/components/toasts/Toasts'
import ExternalLinkBaserowLogo from '@baserow/modules/core/components/ExternalLinkBaserowLogo'
import { getToken } from '@baserow/modules/core/utils/auth'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { renderMarkdown } from '@baserow_enterprise/utils/agentMarkdown'

// Visitors talk to the agent without an account: this page only shows what the
// public endpoints return (their own messages, final answers, a coarse
// status). Nothing else of the agent is loaded here.
definePageMeta({ middleware: ['settings'] })

const route = useRoute()
const nuxtApp = useNuxtApp()
const { $store, $realtime, $config, $i18n } = nuxtApp
const { t } = useI18n()

const originalLocale = ref($i18n.locale.value)
const detectedLocale = useState('public-agent-chat-locale', () => {
  return $i18n.getBrowserLocale() || $i18n.defaultLocale
})
$i18n.locale.value = detectedLocale.value
await $i18n.loadLocaleMessages(detectedLocale.value)

const slug = route.params.slug
const cookieKey = `agent-chat-${slug}`

const { data, error } = await useAsyncData(
  `public-agent-chat-${slug}`,
  async () => {
    const token = await getToken(nuxtApp, cookieKey)
    try {
      await nuxtApp.runWithContext(() =>
        $store.dispatch('publicAgentChat/load', { slug, token })
      )
      return { ok: true }
    } catch (e) {
      const statusCode = e.response?.status
      if (statusCode === 401) {
        return {
          redirect: {
            name: 'agent-public-chat-auth',
            params: { slug },
            query: { original: route.path },
          },
        }
      }
      throw createError({
        statusCode: statusCode === 404 ? 404 : 500,
        message:
          statusCode === 404
            ? 'This chat is not available.'
            : 'Could not load chat.',
        data: { report: false },
        fatal: true,
      })
    }
  }
)
if (error.value) {
  throw error.value
}
if (data.value?.redirect) {
  await navigateTo(data.value.redirect)
}

const info = computed(() => $store.getters['publicAgentChat/getInfo'] || {})
const messages = computed(() => $store.getters['publicAgentChat/getMessages'])
const status = computed(() => $store.getters['publicAgentChat/getStatus'])
const partial = computed(() => $store.getters['publicAgentChat/getPartial'])
const busy = computed(() => $store.getters['publicAgentChat/isBusy'])

useHead(() => ({ title: info.value.title || 'Chat' }))

const draft = ref('')
const input = ref(null)
const scroller = ref(null)
// The same strip the in-app composer shows above its box while a run is
// busy or paused for a team member's approval.
const composerStatus = computed(() => {
  if (status.value === 'waiting_for_approval') {
    return t('publicAgentChat.waitingForApproval')
  }
  if (status.value === 'working') {
    return t('publicAgentChat.working')
  }
  return ''
})
const canSend = computed(() => draft.value.trim() !== '' && !busy.value)

const render = (content) => renderMarkdown(content || '')

const resize = () => {
  const el = input.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 160)}px`
}

const scrollToBottom = async () => {
  await nextTick()
  if (scroller.value) {
    scroller.value.scrollTop = scroller.value.scrollHeight
  }
}
watch([messages, partial, status], scrollToBottom, { deep: true })

// Polling keeps the page honest when the websocket is unavailable or drops a
// message: while the agent works, the transcript is re-read every few seconds.
let pollTimer = null
const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}
const startPolling = () => {
  stopPolling()
  pollTimer = setInterval(async () => {
    if (!busy.value) {
      stopPolling()
      return
    }
    try {
      await $store.dispatch('publicAgentChat/refresh')
    } catch (e) {
      // A transient failure; the next tick retries.
    }
  }, 4000)
}
watch(busy, (value) => (value ? startPolling() : stopPolling()))

// Restarting opens a new conversation while the previous one is still
// subscribed; it is dropped first so its late events don't land in the new one.
let realtimePage = null
const subscribe = () => {
  if ($config.public.disableAnonymousPublicViewWsConnections) {
    return
  }
  $realtime.connect(true, true)
  if (realtimePage !== null) {
    $realtime.unsubscribe(realtimePage.page, realtimePage.params)
  }
  realtimePage = {
    page: 'public_agent_chat',
    params: {
      slug,
      token: $store.getters['publicAgentChat/getToken'],
      conversation: $store.getters['publicAgentChat/getConversationUuid'],
    },
  }
  $realtime.subscribe(realtimePage.page, realtimePage.params)
}

const startConversation = async () => {
  try {
    await $store.dispatch('publicAgentChat/startConversation')
    subscribe()
  } catch (e) {
    notifyIf(e)
  }
}

const restart = async () => {
  if (busy.value) return
  draft.value = ''
  await startConversation()
  input.value?.focus()
}

const send = async () => {
  if (!canSend.value) return
  const content = draft.value.trim()
  draft.value = ''
  await nextTick()
  resize()
  try {
    await $store.dispatch('publicAgentChat/sendMessage', content)
  } catch (e) {
    const code = e.handler?.code
    if (code === 'ERROR_PUBLIC_CHAT_MESSAGE_LIMIT_REACHED') {
      $store.dispatch('toast/error', {
        title: $i18n.t('publicAgentChat.limitTitle'),
        message: $i18n.t('publicAgentChat.limitMessage'),
      })
      e.handler?.handled?.()
    } else if (code === 'ERROR_PUBLIC_CHAT_RATE_LIMIT_EXCEEDED') {
      $store.dispatch('toast/error', {
        title: $i18n.t('publicAgentChat.rateLimitTitle'),
        message: $i18n.t('publicAgentChat.rateLimitMessage'),
      })
      e.handler?.handled?.()
    } else {
      notifyIf(e)
    }
    draft.value = content
  }
  input.value?.focus()
}

onMounted(async () => {
  await startConversation()
  input.value?.focus()
})

onBeforeUnmount(() => {
  stopPolling()
  $i18n.locale.value = originalLocale.value
  if (!$config.public.disableAnonymousPublicViewWsConnections) {
    $realtime.subscribe(null)
    $realtime.disconnect()
  }
})
</script>
