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
    <div
      ref="messagesEl"
      class="agent-chat__messages"
      :class="{ 'agent-chat__messages--welcome': showWelcome }"
    >
      <div class="agent-chat__column">
        <div v-if="loadingConversation" class="agent-chat__loading">
          <div class="loading"></div>
        </div>
        <AgentChatEmptyState
          v-else-if="showWelcome"
          :name="agent?.name || application.name"
          :trigger-label="firstTriggerLabel"
          :identity-name="identityName"
          :can-run-chat="canRunChat"
          :can-run-once="canRunOnce"
          :running-once="runningOnce"
          @prompt="sendPrompt"
          @run-once="$emit('run-once')"
        />
        <template v-for="block in visibleBlocks" :key="block.key">
          <AgentChatTriggerRow
            v-if="block.type === 'trigger'"
            :label="triggerLabel"
            :payload="triggerPayload(block.event)"
          />
          <AgentChatMessage
            v-else-if="block.type === 'message' || block.type === 'system'"
            :event="block.event"
            :attachment-icon="attachmentIcon"
            :format-size="formatSize"
          />
          <AgentChatReasoning
            v-else-if="block.type === 'reasoning'"
            :event="block.event"
            :live="block.live"
          />
          <AgentChatToolGroup
            v-else-if="block.type === 'tool_group'"
            :block="block"
            :tool-label="toolLabel"
            :applications="applications"
          />
          <AgentToolApprovals
            v-else-if="block.type === 'approval_set'"
            :approvals="approvalsForIds(block.ids)"
            :can-decide="canRunChat"
            :disabled="decidingApprovals"
            :agent-name="agent?.name || application.name"
            :tool-label="toolLabel"
            :can-change-tools="canUpdateTools"
            @decide="decideApprovals"
          />
        </template>
        <Alert
          v-if="modelMissing && canRunChat"
          type="warning"
          class="agent-chat__model-notice"
        >
          <template #title>{{ $t('agentChat.modelMissingTitle') }}</template>
          {{ $t('agentChat.modelMissing') }}
          <template #actions>
            <Button
              type="primary"
              size="small"
              @click="$emit('open-configuration', 'settings')"
            >
              {{ $t('agentChat.configureModel') }}
            </Button>
          </template>
        </Alert>
        <div v-if="running && !hasLiveBlock" class="agent-chat__running">
          <div class="loading"></div>
        </div>
        <div
          v-if="hasError && canRunChat && !running"
          class="agent-chat__retry"
        >
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
        :loading="canceling"
        @click="cancel"
      >
        {{ $t('agentChat.cancel') }}
      </Button>
    </div>
    <div v-else-if="canRunChat" class="agent-chat__composer">
      <div class="agent-chat__column">
        <div
          v-if="composerStatus"
          class="agent-chat__composer-status"
          :class="{
            'agent-chat__composer-status--running': running,
            'agent-chat__composer-status--awaiting': awaitingApproval,
          }"
        >
          <i
            class="agent-chat__composer-status-icon"
            :class="
              awaitingApproval ? 'iconoir-shield-check' : 'iconoir-sparks'
            "
          ></i>
          <span class="agent-chat__composer-status-message">
            {{ composerStatus }}
          </span>
        </div>
        <div
          class="agent-chat__composer-box"
          :class="{ 'agent-chat__composer-box--after-status': composerStatus }"
        >
          <div
            v-if="attachments.length > 0"
            class="agent-chat__composer-attachments"
          >
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
          <textarea
            ref="textareaEl"
            v-model="message"
            class="agent-chat__composer-textarea"
            :disabled="awaitingApproval"
            :placeholder="
              awaitingApproval
                ? $t('agentChat.awaitingApprovalPlaceholder')
                : $t('agentChat.inputPlaceholderNamed', {
                    name: agent?.name || application.name,
                  })
            "
            :rows="1"
            @input="adjustHeight"
            @keydown.enter="onEnter"
          ></textarea>
          <div class="agent-chat__composer-row">
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
              <span
                v-if="canceling"
                class="agent-chat__send-button-spinner"
              ></span>
              <i
                v-else-if="!running && !awaitingApproval"
                class="iconoir-arrow-up"
              ></i>
              <i v-else class="iconoir-square"></i>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { defineComponent, ref, reactive, computed, watch, nextTick } from 'vue'
import { useStore } from 'vuex'
import { useNuxtApp, useI18n } from '#imports'
import { notifyIf } from '@baserow/modules/core/utils/error'
import UserFileService from '@baserow/modules/core/services/userFile'
import { mimetype2icon } from '@baserow/modules/core/utils/fileTypeToIcon'
import { formatFileSize } from '@baserow/modules/core/utils/file'
import { uuid as uuidv4 } from '@baserow/modules/core/utils/string'
import {
  groupChatEvents,
  formatToolPayload,
} from '@baserow_enterprise/utils/agentChatEvents'
import AgentToolApprovals from '@baserow_enterprise/components/agentApplication/AgentToolApprovals'
import AgentChatEmptyState from '@baserow_enterprise/components/agentApplication/AgentChatEmptyState'
import AgentChatMessage from '@baserow_enterprise/components/agentApplication/AgentChatMessage'
import AgentChatReasoning from '@baserow_enterprise/components/agentApplication/AgentChatReasoning'
import AgentChatTriggerRow from '@baserow_enterprise/components/agentApplication/AgentChatTriggerRow'
import AgentChatToolGroup from '@baserow_enterprise/components/agentApplication/AgentChatToolGroup'

const MIN_ROWS = 1
const MAX_ROWS = 6
const MAX_FILES = 10

export default defineComponent({
  name: 'AgentChat',
  components: {
    AgentToolApprovals,
    AgentChatEmptyState,
    AgentChatMessage,
    AgentChatReasoning,
    AgentChatTriggerRow,
    AgentChatToolGroup,
  },
  props: {
    runningOnce: {
      type: Boolean,
      required: false,
      default: false,
    },
    application: {
      type: Object,
      required: true,
    },
  },
  emits: ['run-once', 'open-configuration'],
  setup(props) {
    const store = useStore()
    const { $hasPermission, $client, $registry } = useNuxtApp()
    const { t, locale } = useI18n()

    const message = ref('')
    const messagesEl = ref(null)
    const textareaEl = ref(null)
    const fileInputEl = ref(null)
    const attachments = ref([])
    const dragCount = ref(0)
    const decidingApprovals = ref(false)

    const events = computed(() => store.getters['agentChat/getEvents'])
    const running = computed(() => store.getters['agentChat/isRunning'])
    const canceling = computed(() => store.getters['agentChat/isCanceling'])
    // Another conversation is being fetched: the old transcript is replaced
    // by a loader instead of lingering with no sign that anything happens.
    const loadingConversation = computed(
      () => store.getters['agentChat/getLoadingChatUuid'] !== null
    )
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
    const triggers = computed(
      () => store.getters['agentApplication/getTriggers']
    )
    const toolLabel = computed(
      () => store.getters['agentApplication/getToolLabel']
    )
    const identityName = computed(
      () =>
        store.getters['agent/get'](props.application.agent_identity_id)?.name ||
        ''
    )

    const triggerNodeLabel = (triggerType) => {
      for (const candidate of [triggerType, `local_baserow_${triggerType}`]) {
        try {
          return $registry.get('node', candidate).name
        } catch {
          // Not a node type; try the next candidate.
        }
      }
      return ''
    }
    const triggerLabel = computed(
      () =>
        triggerNodeLabel(store.getters['agentChat/getTriggerType']) ||
        t('agentChat.startedByTrigger')
    )
    const triggerPayload = (event) => {
      const payload = store.getters['agentChat/getEventPayload']
      return payload !== null && payload !== undefined
        ? formatToolPayload(payload)
        : formatToolPayload(event.content)
    }
    const firstTriggerLabel = computed(() => {
      const trigger = triggers.value.find((item) => item.enabled)
      return trigger ? triggerNodeLabel(trigger.service?.type) : ''
    })

    const blocks = computed(() =>
      groupChatEvents(events.value, {
        running: running.value,
        chatSource: source.value,
      })
    )
    const visibleBlocks = computed(() =>
      loadingConversation.value ? [] : blocks.value
    )
    const showWelcome = computed(
      () => events.value.length === 0 && !running.value
    )
    // Without a model every run fails; point straight at the fix.
    const modelMissing = computed(
      () =>
        agent.value !== null &&
        (!agent.value.ai_generative_ai_type ||
          !agent.value.ai_generative_ai_model)
    )
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
    const canUpdateTools = computed(() =>
      $hasPermission(
        'agent_application.update_tool',
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
        return !canCancelChat.value || canceling.value
      }
      return sending.value || uploading.value || message.value.trim() === ''
    })

    const pendingToolApprovals = computed(
      () => store.getters['agentChat/getPendingToolApprovals']
    )
    const composerStatus = computed(() => {
      if (awaitingApproval.value) {
        return t('agentChat.waitingForApproval', {
          count: pendingToolApprovals.value.length,
        })
      }
      if (running.value) {
        return runningMessage.value || t('agentChat.statusThinking')
      }
      return ''
    })

    // While the run is in progress the last reasoning event streams live and
    // a tool group shows its own "Working on it" state (the loader is hidden
    // then); the running loader covers the rest.
    const hasLiveBlock = computed(() => {
      const last = blocks.value.at(-1)
      return Boolean(
        last &&
        (last.type === 'reasoning' || last.type === 'tool_group') &&
        last.live
      )
    })
    const applications = computed(() => store.getters['application/getAll'])

    // Follow new events and the growing live streaming text, but only while
    // the user is (near) the bottom; someone reading older messages must not
    // be yanked down. A `pre` watcher runs before the DOM updates, so the
    // scroll metrics still describe the old content.
    const AT_BOTTOM_THRESHOLD = 40
    const isScrolledToBottom = () => {
      const el = messagesEl.value
      return (
        !el ||
        el.scrollHeight - el.scrollTop - el.clientHeight <= AT_BOTTOM_THRESHOLD
      )
    }
    const scrollToBottom = async () => {
      await nextTick()
      if (messagesEl.value) {
        messagesEl.value.scrollTop = messagesEl.value.scrollHeight
      }
    }
    watch(
      () => [
        events.value.length,
        events.value[events.value.length - 1]?.content,
      ],
      () => {
        if (isScrolledToBottom()) {
          scrollToBottom()
        }
      }
    )
    // Opening another conversation always starts at its end.
    watch(currentChatUuid, () => scrollToBottom())

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
      scrollToBottom()
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

    const sendPrompt = async (text) => {
      message.value = text
      await nextTick()
      adjustHeight()
      await send()
    }

    const canRunOnce = computed(
      () =>
        canRunChat.value && triggers.value.some((trigger) => trigger.enabled)
    )

    const decideApprovals = async ({ decisions, dontAskAgain }) => {
      if (decidingApprovals.value) {
        return
      }
      decidingApprovals.value = true
      try {
        await store.dispatch('agentChat/decideApprovals', {
          decisions,
          dontAskAgain,
        })
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

    const approvalsForIds = (ids) =>
      ids
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
      events,
      blocks,
      showWelcome,
      modelMissing,
      toolLabel,
      identityName,
      triggerLabel,
      triggerPayload,
      firstTriggerLabel,
      canRunOnce,
      sendPrompt,
      running,
      canceling,
      loadingConversation,
      visibleBlocks,
      sending,
      runningMessage,
      agent,
      canRunChat,
      canCancelChat,
      canUpdateTools,
      watchingExternalRun,
      sendButtonDisabled,
      composerStatus,
      awaitingApproval,
      decidingApprovals,
      attachments,
      dragging,
      hasLiveBlock,
      applications,
      adjustHeight,
      send,
      cancel,
      onEnter,
      onButtonClick,
      decideApprovals,
      approvalsForIds,
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
