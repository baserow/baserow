<template>
  <div
    class="agent-chat"
    @dragenter.prevent="onDragEnter"
    @dragover.prevent
    @dragleave="onDragLeave"
    @drop.prevent="onDrop"
  >
    <div v-if="dragging" class="agent-chat__dropzone">
      <i class="iconoir-attachment agent-chat__dropzone-icon"></i>
      <span>{{ $t('agentChat.dropFiles') }}</span>
    </div>
    <div ref="messagesEl" class="agent-chat__messages">
      <div v-if="events.length === 0" class="agent-chat__empty">
        <i class="agent-chat__empty-icon baserow-icon-agent"></i>
        <div class="agent-chat__empty-title">
          {{
            agent?.name
              ? $t('agentChat.emptyTitleNamed', { name: agent.name })
              : $t('agentChat.emptyTitle')
          }}
        </div>
        <div class="agent-chat__empty-message">
          {{
            canRunChat
              ? $t('agentChat.emptyMessage')
              : $t('agentChat.emptyMessageReadOnly')
          }}
        </div>
      </div>
      <template v-for="(event, index) in events">
        <div
          v-if="event.type === 'human'"
          :key="index"
          class="agent-chat__message agent-chat__message--human"
        >
          <div class="agent-chat__message-content">{{ event.content }}</div>
          <div
            v-if="event.attachments && event.attachments.length > 0"
            class="agent-chat__message-attachments"
          >
            <div
              v-for="(attachment, attachmentIndex) in event.attachments"
              :key="attachmentIndex"
              class="agent-chat__attachment-chip"
            >
              <i
                class="agent-chat__attachment-chip-icon"
                :class="attachmentIcon(attachment)"
              ></i>
              <span class="agent-chat__attachment-chip-name">{{
                attachment.visible_name ||
                attachment.original_name ||
                attachment.name
              }}</span>
              <span
                v-if="attachment.size"
                class="agent-chat__attachment-chip-size"
                >{{ formatSize(attachment.size) }}</span
              >
            </div>
          </div>
        </div>
        <div
          v-else-if="event.type === 'system'"
          :key="`system-${index}`"
          class="agent-chat__message agent-chat__message--system"
        >
          {{ event.content }}
        </div>
        <!-- eslint-disable vue/no-v-html -->
        <div
          v-else-if="event.type === 'ai/message'"
          :key="`ai-${index}`"
          class="agent-chat__message agent-chat__message--ai"
          v-html="formatMessage(event.content)"
        ></div>
        <!-- eslint-enable vue/no-v-html -->
        <div
          v-else-if="event.type === 'ai/error'"
          :key="`error-${index}`"
          class="agent-chat__message agent-chat__message--error"
        >
          {{ event.content }}
        </div>
        <div
          v-else-if="event.type === 'ai/cancelled'"
          :key="`cancelled-${index}`"
          class="agent-chat__message agent-chat__message--system"
        >
          {{ $t('agentChat.cancelled') }}
        </div>
        <!-- eslint-disable vue/no-v-html -->
        <div
          v-else-if="event.type === 'ai/reasoning'"
          :key="`reasoning-${index}`"
          class="agent-chat__reasoning"
          :class="{
            'agent-chat__reasoning--live': isLiveReasoning(event, index),
          }"
        >
          <span
            v-if="isLiveReasoning(event, index)"
            class="agent-chat__reasoning-indicator"
          ></span>
          <div
            class="agent-chat__reasoning-text"
            :class="{
              'agent-chat__reasoning-text--collapsed':
                !isLiveReasoning(event, index) && !expandedReasoning[index],
            }"
            v-html="formatMessage(event.content)"
          ></div>
          <button
            v-if="!isLiveReasoning(event, index)"
            class="agent-chat__reasoning-toggle"
            @click="toggleReasoning(index)"
          >
            <i
              class="iconoir-nav-arrow-down agent-chat__reasoning-chevron"
              :class="{
                'agent-chat__reasoning-chevron--expanded':
                  expandedReasoning[index],
              }"
            ></i>
          </button>
        </div>
        <!-- eslint-enable vue/no-v-html -->
        <div
          v-else-if="event.type === 'tool_call'"
          :key="`tool-${index}`"
          class="agent-chat__tool-call"
        >
          <i
            class="agent-chat__tool-call-icon"
            :class="toolCallIcon(event)"
          ></i>
          <span class="agent-chat__tool-call-name">{{ event.tool_name }}</span>
        </div>
        <AgentToolApprovals
          v-else-if="event.type === 'approval_set'"
          :key="`approvals-${index}`"
          :approvals="approvalsForEvent(event)"
          :can-decide="canRunChat"
          :disabled="decidingApprovals"
          @decide="decideApprovals"
        />
      </template>
      <div v-if="running && !hasLiveReasoning" class="agent-chat__running">
        <div class="loading"></div>
      </div>
      <div v-if="hasError && canRunChat && !running" class="agent-chat__retry">
        <Button
          type="secondary"
          size="small"
          icon="iconoir-refresh"
          :loading="retrying"
          @click="retry"
        >
          {{ $t('agentChat.retry') }}
        </Button>
      </div>
    </div>
    <div
      v-if="watchingExternalRun"
      class="agent-chat__banner"
      data-banner-type="external-run"
    >
      <div class="loading"></div>
      <span class="agent-chat__banner-text">
        {{ $t('agentChat.externalRunBanner') }}
      </span>
      <Button
        v-if="canCancelChat"
        type="secondary"
        icon="iconoir-square"
        @click="cancel"
      >
        {{ $t('agentChat.cancel') }}
      </Button>
    </div>
    <div v-else-if="canRunChat" class="agent-chat__input">
      <div
        class="agent-chat__input-status"
        :class="{
          'agent-chat__input-status--running': running,
          'agent-chat__input-status--awaiting': awaitingApproval,
        }"
      >
        <i
          class="agent-chat__input-status-icon"
          :class="
            awaitingApproval ? 'iconoir-warning-triangle' : 'iconoir-sparks'
          "
        ></i>
        <span class="agent-chat__input-status-message">
          {{ inputStatusMessage }}
        </span>
      </div>
      <div class="agent-chat__input-wrapper">
        <div v-if="attachments.length > 0" class="agent-chat__attachments">
          <div
            v-for="attachment in attachments"
            :key="attachment.key"
            class="agent-chat__attachment-chip"
          >
            <div
              v-if="attachment.uploading"
              class="agent-chat__attachment-chip-loading"
            ></div>
            <i
              v-else
              class="agent-chat__attachment-chip-icon"
              :class="attachmentIcon(attachment.data)"
            ></i>
            <span class="agent-chat__attachment-chip-name">{{
              attachment.file.name
            }}</span>
            <span class="agent-chat__attachment-chip-size">{{
              formatSize(attachment.file.size)
            }}</span>
            <a
              class="agent-chat__attachment-chip-remove"
              :title="$t('agentChat.removeAttachment')"
              @click.prevent="removeAttachment(attachment)"
            >
              <i class="iconoir-cancel"></i>
            </a>
          </div>
        </div>
        <div class="agent-chat__input-row">
          <button
            class="agent-chat__attach-button"
            :disabled="awaitingApproval"
            :title="$t('agentChat.attachFiles')"
            @click="openFilePicker"
          >
            <i class="iconoir-attachment"></i>
          </button>
          <input
            ref="fileInputEl"
            type="file"
            multiple
            class="agent-chat__file-input"
            @change="onFileInputChange"
          />
          <textarea
            ref="textareaEl"
            v-model="message"
            class="agent-chat__input-textarea"
            :disabled="awaitingApproval"
            :placeholder="
              awaitingApproval
                ? $t('agentChat.awaitingApprovalPlaceholder')
                : $t('agentChat.inputPlaceholder')
            "
            :rows="1"
            @input="adjustHeight"
            @keydown.enter="onEnter"
          ></textarea>
        </div>
        <button
          class="agent-chat__send-button"
          :class="{
            'agent-chat__send-button--disabled': sendButtonDisabled,
          }"
          :disabled="sendButtonDisabled"
          :title="
            awaitingApproval
              ? $t('agentChat.rejectAll')
              : running
                ? $t('agentChat.cancel')
                : $t('agentChat.send')
          "
          @click="onButtonClick"
        >
          <i v-if="!running && !awaitingApproval" class="iconoir-arrow-up"></i>
          <i v-else class="iconoir-square"></i>
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import { defineComponent, ref, reactive, computed, watch, nextTick } from 'vue'
import { useStore } from 'vuex'
import { useNuxtApp, useI18n } from '#imports'
import MarkdownIt from 'markdown-it'
import { notifyIf } from '@baserow/modules/core/utils/error'
import UserFileService from '@baserow/modules/core/services/userFile'
import { mimetype2icon } from '@baserow/modules/core/utils/fileTypeToIcon'
import { formatFileSize } from '@baserow/modules/core/utils/file'
import { uuid as uuidv4 } from '@baserow/modules/core/utils/string'
import AgentToolApprovals from '@baserow_enterprise/components/agentApplication/AgentToolApprovals'

// Initialize markdown parser with safe settings.
const md = new MarkdownIt({
  html: false, // Disable HTML tags for security
  linkify: true, // Auto-convert URLs to links
  typographer: true, // Enable smart quotes and other typography
  breaks: false,
})

const MIN_ROWS = 1
const MAX_ROWS = 6
const MAX_FILES = 10

export default defineComponent({
  name: 'AgentChat',
  components: { AgentToolApprovals },
  props: {
    application: {
      type: Object,
      required: true,
    },
  },
  setup(props) {
    const store = useStore()
    const { $hasPermission, $client } = useNuxtApp()
    const { t, locale } = useI18n()

    const message = ref('')
    const messagesEl = ref(null)
    const textareaEl = ref(null)
    const fileInputEl = ref(null)
    const expandedReasoning = reactive({})
    const attachments = ref([])
    const dragCount = ref(0)
    const decidingApprovals = ref(false)

    const events = computed(() => store.getters['agentChat/getEvents'])
    const running = computed(() => store.getters['agentChat/isRunning'])
    const hasError = computed(() => store.getters['agentChat/hasError'])
    const retrying = ref(false)
    const retry = async () => {
      retrying.value = true
      try {
        await store.dispatch('agentChat/retryChat')
      } catch (error) {
        notifyIf(error, 'application')
      } finally {
        retrying.value = false
      }
    }
    const sending = computed(() => store.getters['agentChat/isSending'])
    const runningMessage = computed(
      () => store.getters['agentChat/getRunningMessage']
    )
    const currentChatUuid = computed(
      () => store.getters['agentChat/getCurrentChatUuid']
    )
    const source = computed(() => store.getters['agentChat/getSource'])
    const agent = computed(() => store.getters['agentApplication/getAgent'])
    const awaitingApproval = computed(
      () => store.getters['agentChat/isAwaitingApproval']
    )
    const toolApprovals = computed(
      () => store.getters['agentChat/getToolApprovals']
    )

    const canRunChat = computed(() =>
      $hasPermission(
        'agent_application.run_chat',
        props.application,
        props.application.workspace.id
      )
    )
    const canCancelChat = computed(() =>
      $hasPermission(
        'agent_application.cancel_chat',
        props.application,
        props.application.workspace.id
      )
    )

    // A conversation started by a trigger or during setup that is still
    // running is watched live; the input only appears once it has finished so
    // the user can continue the conversation manually.
    const watchingExternalRun = computed(
      () => running.value && source.value !== 'manual'
    )

    const uploading = computed(() =>
      attachments.value.some((attachment) => attachment.uploading)
    )

    const sendButtonDisabled = computed(() => {
      if (running.value || awaitingApproval.value) {
        return !canCancelChat.value
      }
      return sending.value || uploading.value || message.value.trim() === ''
    })

    const inputStatusMessage = computed(() => {
      if (awaitingApproval.value) {
        return t('agentChat.statusAwaitingApproval')
      }
      if (running.value) {
        return runningMessage.value || t('agentChat.statusThinking')
      }
      return t('agentChat.statusWaiting')
    })

    const formatMessage = (content) => {
      if (!content) return ''
      return md.render(content)
    }

    // While the run is in progress, the last reasoning event renders expanded
    // as live streaming text; on finalize it becomes a collapsed reasoning
    // row that can be opened again later.
    const isLiveReasoning = (event, index) => {
      return (
        running.value &&
        event.type === 'ai/reasoning' &&
        index === events.value.length - 1
      )
    }

    const hasLiveReasoning = computed(() => {
      const lastIndex = events.value.length - 1
      return (
        lastIndex >= 0 && isLiveReasoning(events.value[lastIndex], lastIndex)
      )
    })

    const toggleReasoning = (index) => {
      expandedReasoning[index] = !expandedReasoning[index]
    }

    // Follow both new events and the growing live streaming text.
    watch(
      () => [
        events.value.length,
        events.value[events.value.length - 1]?.content,
      ],
      async () => {
        await nextTick()
        if (messagesEl.value) {
          messagesEl.value.scrollTop = messagesEl.value.scrollHeight
        }
      }
    )

    const toolCallIcon = (event) => {
      if (event.result === null) {
        return 'iconoir-refresh-double'
      }
      return event.result.status === 'ok'
        ? 'iconoir-check-circle'
        : 'iconoir-warning-circle'
    }

    const adjustHeight = () => {
      const textarea = textareaEl.value
      if (!textarea) return

      const computedStyle = window.getComputedStyle(textarea)
      const lineHeight = parseInt(computedStyle.lineHeight) || 20

      // Reset height to auto to get the correct scrollHeight.
      textarea.style.height = 'auto'
      const minHeight = lineHeight * MIN_ROWS
      const maxHeight = lineHeight * MAX_ROWS
      const newHeight = Math.max(
        minHeight,
        Math.min(textarea.scrollHeight, maxHeight)
      )
      textarea.style.height = `${newHeight}px`
      textarea.style.overflowY =
        textarea.scrollHeight > maxHeight ? 'auto' : 'hidden'
    }

    const send = async () => {
      const content = message.value.trim()
      if (
        content === '' ||
        running.value ||
        sending.value ||
        awaitingApproval.value ||
        uploading.value
      ) {
        return
      }
      const sentAttachments = attachments.value
      const userFiles = sentAttachments
        .filter((attachment) => attachment.data !== null)
        .map((attachment) => attachment.data)
      message.value = ''
      attachments.value = []
      await nextTick()
      adjustHeight()
      try {
        await store.dispatch('agentChat/sendMessage', {
          application: props.application,
          content,
          userFiles,
        })
      } catch (error) {
        message.value = content
        attachments.value = sentAttachments
        notifyIf(error, 'application')
      }
    }

    const cancel = async () => {
      try {
        await store.dispatch('agentChat/cancel', {
          chatUuid: currentChatUuid.value,
        })
      } catch (error) {
        notifyIf(error, 'application')
      }
    }

    const onEnter = (event) => {
      // Shift+Enter keeps the default behavior (new line).
      if (!event.shiftKey) {
        event.preventDefault()
        if (!running.value) {
          send()
        }
      }
    }

    const onButtonClick = () => {
      if (running.value || awaitingApproval.value) {
        cancel()
      } else {
        send()
      }
    }

    const decideApprovals = async (decisions) => {
      if (decidingApprovals.value) {
        return
      }
      decidingApprovals.value = true
      try {
        await store.dispatch('agentChat/decideApprovals', { decisions })
      } catch (error) {
        if (
          error.handler &&
          error.handler.code === 'ERROR_AGENT_TOOL_APPROVAL_DOES_NOT_EXIST'
        ) {
          // Another collaborator already decided this approval; refetch so
          // the latest decisions become visible.
          error.handler.handled()
          try {
            await store.dispatch('agentChat/openConversation', {
              applicationId: props.application.id,
              chatUuid: currentChatUuid.value,
            })
          } catch (refetchError) {
            notifyIf(refetchError, 'application')
          }
        } else {
          notifyIf(error, 'application')
        }
      } finally {
        decidingApprovals.value = false
      }
    }

    const approvalsById = computed(
      () =>
        new Map(toolApprovals.value.map((approval) => [approval.id, approval]))
    )

    const approvalsForEvent = (event) =>
      event.ids
        .map((id) => approvalsById.value.get(id))
        .filter((approval) => approval !== undefined)

    const attachmentIcon = (attachment) => mimetype2icon(attachment?.mime_type)

    const formatSize = (bytes) => formatFileSize(t, locale.value, bytes)

    const canAttach = computed(
      () => canRunChat.value && !awaitingApproval.value
    )

    const dragging = computed(() => dragCount.value > 0)

    const uploadFile = async (file) => {
      const entry = reactive({
        key: uuidv4(),
        file: { name: file.name, size: file.size },
        uploading: true,
        data: null,
      })
      attachments.value.push(entry)
      try {
        const { data } = await UserFileService($client).uploadFile(file)
        entry.data = data
        entry.uploading = false
      } catch (error) {
        attachments.value = attachments.value.filter((a) => a !== entry)
        notifyIf(error, 'userFile')
      }
    }

    const addFiles = (fileList) => {
      const files = Array.from(fileList || [])
      if (files.length === 0) {
        return
      }
      const available = MAX_FILES - attachments.value.length
      if (files.length > available) {
        store.dispatch('toast/error', {
          title: t('agentChat.tooManyFilesTitle'),
          message: t('agentChat.tooManyFiles', { max: MAX_FILES }),
        })
      }
      for (const file of files.slice(0, Math.max(available, 0))) {
        uploadFile(file)
      }
    }

    const removeAttachment = (attachment) => {
      attachments.value = attachments.value.filter((a) => a !== attachment)
    }

    const openFilePicker = () => {
      fileInputEl.value?.click()
    }

    const onFileInputChange = (event) => {
      addFiles(event.target.files)
      // Reset so the same file can be selected again later.
      event.target.value = ''
    }

    const onDragEnter = (event) => {
      if (!canAttach.value || !event.dataTransfer?.types?.includes('Files')) {
        return
      }
      dragCount.value++
    }

    const onDragLeave = () => {
      if (dragCount.value > 0) {
        dragCount.value--
      }
    }

    const onDrop = (event) => {
      dragCount.value = 0
      if (!canAttach.value) {
        return
      }
      addFiles(event.dataTransfer?.files)
    }

    // Attachments staged in the input belong to the conversation they were
    // added to; drop them when another conversation is opened.
    watch(currentChatUuid, () => {
      attachments.value = []
    })

    return {
      hasError,
      retrying,
      retry,
      message,
      messagesEl,
      textareaEl,
      fileInputEl,
      expandedReasoning,
      events,
      running,
      sending,
      runningMessage,
      agent,
      canRunChat,
      canCancelChat,
      watchingExternalRun,
      sendButtonDisabled,
      inputStatusMessage,
      awaitingApproval,
      decidingApprovals,
      attachments,
      dragging,
      formatMessage,
      isLiveReasoning,
      hasLiveReasoning,
      toggleReasoning,
      toolCallIcon,
      adjustHeight,
      send,
      cancel,
      onEnter,
      onButtonClick,
      decideApprovals,
      approvalsForEvent,
      attachmentIcon,
      formatSize,
      removeAttachment,
      openFilePicker,
      onFileInputChange,
      onDragEnter,
      onDragLeave,
      onDrop,
    }
  },
})
</script>
