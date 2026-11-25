import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useNuxtApp } from '#app'

import {
  RUN_FINISHED,
  STREAM_IDLE_MS,
} from '@baserow/modules/core/chatRuns/constants'
import {
  foldRunEvent,
  initialRunView,
} from '@baserow/modules/core/chatRuns/fold'
import { generateUUID, uuid } from '@baserow/modules/core/utils/string'
import { API_ERROR_CODE, MESSAGE_ROLE } from '@baserow/modules/agent/constants'
import { AGENT_REPLY_STATUS } from '@baserow/modules/agent/utils/replies'
import PublicAgentChatService from '@baserow_enterprise/services/publicAgentChat'

const STREAM_RETRY_MS = 2000
const MAX_RETRY_MS = 30000
const WAITING_SYNC_MS = 5000
const REFUSED_STATUSES = [401, 404]
const SYNC_ERRORS = [
  API_ERROR_CODE.CHAT_RUN_IN_PROGRESS,
  API_ERROR_CODE.AGENT_CONVERSATION_WAITING_FOR_APPROVAL,
]
const UNFINISHED_STATUSES = [
  AGENT_REPLY_STATUS.QUEUED,
  AGENT_REPLY_STATUS.RUNNING,
  AGENT_REPLY_STATUS.WAITING,
]

const isRefused = (error) => REFUSED_STATUSES.includes(error.response?.status)
const isChannelGone = (error) =>
  error.response?.data?.error === API_ERROR_CODE.AGENT_CHANNEL_DOES_NOT_EXIST
const mergeById = (messages, accepted) => [
  ...messages,
  ...accepted.filter(
    ({ id }) => !messages.some((message) => message.id === id)
  ),
]

/**
 * A visitor's conversation in a public chat: its tokens, its messages and the
 * reply being written, which is followed through the run's stream.
 *
 * @param {string} slug The slug of the public chat.
 * @param {object} initialInfo The chat's info as read without a token.
 * @returns {object} The conversation's state and actions.
 */
export function usePublicAgentChat(slug, initialInfo) {
  const service = PublicAgentChatService(useNuxtApp().$client)
  const storageKey = `baserow-agent-public-chat:${slug}`

  const info = ref(initialInfo)
  const tokens = reactive({ accessToken: null, conversationToken: null })
  const savedMessages = ref([])
  const runId = ref(null)
  const runView = ref(initialRunView())
  const passwordError = ref(false)
  const sending = ref(false)
  const sendError = ref(false)
  const unavailable = ref(false)
  const restoreFailed = ref(false)

  let cursor = null
  let streamController = null
  let idleTimer = null
  let syncTimer = null
  let acceptedSends = 0
  let historyLoaded = false
  let failedSyncs = 0
  // Resending the content of a send whose answer was lost must not run it twice.
  let pendingSend = null
  let unmounted = false

  const token = () => tokens.conversationToken || tokens.accessToken
  const needsPassword = computed(() => !info.value.has_access)
  const messages = computed(() => {
    const last = savedMessages.value.at(-1)
    if (!runId.value || last?.role !== MESSAGE_ROLE.ASSISTANT) {
      return savedMessages.value
    }
    return [
      ...savedMessages.value.slice(0, -1),
      { ...last, content: runView.value.text || last.content },
    ]
  })
  const latestStatus = computed(() => savedMessages.value.at(-1)?.status)
  const replying = computed(() =>
    [AGENT_REPLY_STATUS.QUEUED, AGENT_REPLY_STATUS.RUNNING].includes(
      latestStatus.value
    )
  )
  const waiting = computed(
    () => latestStatus.value === AGENT_REPLY_STATUS.WAITING
  )

  function readTokens() {
    try {
      Object.assign(tokens, JSON.parse(localStorage.getItem(storageKey)))
    } catch {}
  }

  function setTokens(values) {
    Object.assign(tokens, values)
    try {
      localStorage.setItem(storageKey, JSON.stringify(tokens))
    } catch {}
  }

  function scheduleSync(delay) {
    clearTimeout(syncTimer)
    if (!unmounted) syncTimer = setTimeout(sync, delay)
  }

  function keepSyncing(delay) {
    if (UNFINISHED_STATUSES.includes(latestStatus.value) && !streamController) {
      scheduleSync(delay)
    }
  }

  function stopFollowing() {
    clearTimeout(idleTimer)
    streamController?.abort()
    streamController = null
  }

  function markUnavailable() {
    unavailable.value = true
    stopFollowing()
    clearTimeout(syncTimer)
  }

  function finishReply(message) {
    stopFollowing()
    runId.value = null
    if (!message) {
      sync()
      return
    }
    savedMessages.value = [...savedMessages.value.slice(0, -1), message]
    keepSyncing(WAITING_SYNC_MS)
  }

  function openStream() {
    const controller = new AbortController()
    streamController = controller
    const ended = () => {
      if (streamController !== controller) return
      stopFollowing()
      scheduleSync(STREAM_RETRY_MS)
    }
    const restartIdleTimer = () => {
      clearTimeout(idleTimer)
      idleTimer = setTimeout(ended, STREAM_IDLE_MS)
    }
    const accept = (record) => {
      if (streamController !== controller) return
      restartIdleTimer()
      if (record.cursor) cursor = record.cursor
      if (record.kind === RUN_FINISHED) {
        finishReply(record.data.message)
      } else {
        runView.value = foldRunEvent(runView.value, record)
      }
    }
    restartIdleTimer()
    service
      .stream(slug, runId.value, cursor, token(), accept, controller.signal)
      .then(ended, ended)
  }

  function follow(id) {
    if (id === runId.value && streamController) return
    stopFollowing()
    if (id !== runId.value) {
      cursor = null
      runView.value = initialRunView()
    }
    runId.value = id
    if (id && !unmounted) openStream()
  }

  function forgetConversation() {
    stopFollowing()
    clearTimeout(syncTimer)
    runId.value = null
    savedMessages.value = []
    restoreFailed.value = false
    setTokens({ conversationToken: null })
  }

  async function sync() {
    const conversationToken = tokens.conversationToken
    if (!conversationToken || unavailable.value) return
    const sendsBefore = acceptedSends
    try {
      const { data } = await service.getConversation(slug, conversationToken)
      if (tokens.conversationToken !== conversationToken || unavailable.value) {
        return
      }
      // The send accepted meanwhile added only its own messages.
      if (acceptedSends !== sendsBefore) return await sync()
      historyLoaded = true
      restoreFailed.value = false
      failedSyncs = 0
      savedMessages.value = data.messages
      follow(data.run_id)
      keepSyncing(WAITING_SYNC_MS)
    } catch (error) {
      if (tokens.conversationToken !== conversationToken) return
      if (isChannelGone(error)) {
        markUnavailable()
      } else if (isRefused(error)) {
        await handleRefusal(error)
      } else {
        const delay = Math.min(
          STREAM_RETRY_MS * 2 ** failedSyncs++,
          MAX_RETRY_MS
        )
        if (historyLoaded) {
          keepSyncing(delay)
        } else {
          restoreFailed.value = true
          scheduleSync(delay)
        }
      }
    }
  }

  async function refreshInfo() {
    try {
      const { data } = await service.getInfo(slug, token())
      info.value = data
    } catch (error) {
      if (!isChannelGone(error)) throw error
      markUnavailable()
    }
  }

  async function reloadInfo() {
    try {
      await refreshInfo()
      if (!unavailable.value && !info.value.has_access) {
        setTokens({ accessToken: null })
      }
    } catch {}
  }

  /** The chat may have a password since, which the reloaded info tells. */
  async function handleRefusal(error) {
    pendingSend = null
    if (tokens.conversationToken) {
      forgetConversation()
    } else if (error.response.status === 401) {
      setTokens({ accessToken: null })
    }
    await reloadInfo()
  }

  async function authorize(password) {
    passwordError.value = false
    try {
      const { data } = await service.authorize(slug, password)
      setTokens({ accessToken: data.access_token })
    } catch (error) {
      if (isChannelGone(error)) {
        markUnavailable()
        return
      }
      if (error.response?.status !== 401) throw error
      passwordError.value = true
      return
    }
    await refreshInfo()
  }

  async function postMessage({ content, key, messageUuid }) {
    if (tokens.conversationToken) {
      return await service.sendMessage(
        slug,
        { uuid: messageUuid, content },
        tokens.conversationToken
      )
    }
    const response = await service.startConversation(
      slug,
      { key, content },
      tokens.accessToken
    )
    historyLoaded = true
    restoreFailed.value = false
    setTokens({ conversationToken: response.data.token })
    return response
  }

  async function handleSendError(error) {
    const code = error.response?.data?.error
    if (code === API_ERROR_CODE.AGENT_CHANNEL_DOES_NOT_EXIST) {
      markUnavailable()
      return
    }
    if (SYNC_ERRORS.includes(code)) {
      sync()
      return
    }
    sendError.value = true
    if (isRefused(error)) await handleRefusal(error)
  }

  /**
   * @param {string} content The visitor's message.
   * @returns {Promise<boolean>} Whether the message was accepted.
   */
  async function send(content) {
    sending.value = true
    sendError.value = false
    if (pendingSend?.content !== content) {
      // The key is the visitor's secret, so it comes from the crypto generator.
      pendingSend = { content, key: generateUUID(), messageUuid: uuid() }
    }
    try {
      const { data } = await postMessage(pendingSend)
      pendingSend = null
      acceptedSends += 1
      savedMessages.value = mergeById(savedMessages.value, data.messages)
      follow(data.run_id)
      return true
    } catch (error) {
      await handleSendError(error)
      return false
    } finally {
      sending.value = false
    }
  }

  async function stop() {
    try {
      await service.stop(slug, tokens.conversationToken)
    } catch (error) {
      if (isChannelGone(error)) markUnavailable()
    }
  }

  function reset() {
    forgetConversation()
    pendingSend = null
    sendError.value = false
  }

  onMounted(async () => {
    readTokens()
    if (!info.value.has_access && token()) await reloadInfo()
    if (tokens.conversationToken) await sync()
  })

  onBeforeUnmount(() => {
    unmounted = true
    stopFollowing()
    clearTimeout(syncTimer)
  })

  return {
    info,
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
    sync,
  }
}
