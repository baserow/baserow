<template>
  <div class="agent-chat-tool-group">
    <a class="agent-chat-tool-group__header" @click.prevent="toggle">
      <span
        class="agent-chat-tool-group__status"
        :class="{
          'agent-chat-tool-group__status--live': block.live,
          'agent-chat-tool-group__status--error': !block.live && block.hasError,
          'agent-chat-tool-group__status--ok': !block.live && !block.hasError,
        }"
      >
        <span v-if="block.live" class="agent-chat-tool-group__spinner"></span>
        <i
          v-else
          :class="
            block.hasError ? 'iconoir-warning-circle' : 'iconoir-check-circle'
          "
        ></i>
      </span>
      <span class="agent-chat-tool-group__title">
        {{ block.live ? $t('agentChat.workingOn') : $t('agentChat.workedOn') }}
      </span>
      <span class="agent-chat-tool-group__count">
        · {{ $t('agentChat.steps', { count: block.toolCount }) }}
      </span>
      <i
        class="iconoir-nav-arrow-right agent-chat-tool-group__chevron"
        :class="{ 'agent-chat-tool-group__chevron--expanded': expanded }"
      ></i>
    </a>
    <div v-if="expanded" class="agent-chat-tool-group__steps">
      <div
        v-for="step in block.steps"
        :key="step.key"
        class="agent-chat-tool-group__step"
        :class="`agent-chat-tool-group__step--${step.kind}`"
      >
        <template v-if="step.kind === 'tool'">
          <div class="agent-chat-tool-group__step-row">
            <span
              class="agent-chat-tool-group__step-status"
              :class="stepStatusClass(step.event)"
            >
              <span
                v-if="!step.event.result && block.live"
                class="agent-chat-tool-group__spinner"
              ></span>
              <i v-else :class="stepIcon(step.event)"></i>
            </span>
            <span class="agent-chat-tool-group__step-label">
              {{ toolLabel(step.event.tool_name) }}
            </span>
            <code class="agent-chat-tool-group__step-id">{{
              step.event.tool_name
            }}</code>
            <a
              v-if="step.event.result"
              class="agent-chat-tool-group__step-toggle"
              @click.prevent="toggleResult(step.key)"
            >
              {{
                expandedResults[step.key]
                  ? $t('agentChat.hideResult')
                  : $t('agentChat.showResult')
              }}
            </a>
          </div>
          <div
            v-if="summary(step.event)"
            class="agent-chat-tool-group__step-summary"
          >
            {{ summary(step.event) }}
          </div>
          <pre
            v-if="expandedResults[step.key] && step.event.result"
            class="agent-chat-tool-group__step-result"
            >{{ formatToolPayload(step.event.result.content) }}</pre
          >
          <div
            v-if="actions(step.event).length > 0"
            class="agent-chat-tool-group__step-actions"
          >
            <Button
              v-for="action in actions(step.event)"
              :key="action.key"
              type="secondary"
              size="small"
              :to="action.to"
              target="_blank"
              icon="iconoir-open-new-window"
            >
              {{ action.label }}
            </Button>
          </div>
        </template>
        <AgentChatReasoning v-else :event="step.event" />
      </div>
    </div>
  </div>
</template>

<script>
import { defineComponent, ref, reactive, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  formatToolPayload,
  summarizeToolArgs,
} from '@baserow_enterprise/utils/agentChatEvents'
import { getToolActions } from '@baserow_enterprise/utils/agentToolActions'
import AgentChatReasoning from '@baserow_enterprise/components/agentApplication/AgentChatReasoning'

export default defineComponent({
  name: 'AgentChatToolGroup',
  components: { AgentChatReasoning },
  props: {
    block: {
      type: Object,
      required: true,
    },
    toolLabel: {
      type: Function,
      required: true,
    },
    applications: {
      type: Array,
      required: false,
      default: () => [],
    },
  },
  setup(props) {
    const { t } = useI18n()
    // Open while the agent is still working, folded once it is done; the
    // user can reopen it afterwards.
    const expanded = ref(props.block.live)
    const userToggled = ref(false)
    watch(
      () => props.block.live,
      (live) => {
        if (!userToggled.value) {
          expanded.value = live
        }
      }
    )
    const toggle = () => {
      userToggled.value = true
      expanded.value = !expanded.value
    }
    const expandedResults = reactive({})
    const toggleResult = (key) => {
      expandedResults[key] = !expandedResults[key]
    }
    const stepIcon = (event) => {
      // A call without a result once the run stopped was deferred (e.g. it
      // is waiting for approval) or never returned.
      if (!event.result) return 'iconoir-clock'
      return event.result.status === 'error'
        ? 'iconoir-warning-circle'
        : 'iconoir-check-circle'
    }
    const stepStatusClass = (event) => {
      if (!event.result) return 'agent-chat-tool-group__step-status--live'
      return event.result.status === 'error'
        ? 'agent-chat-tool-group__step-status--error'
        : 'agent-chat-tool-group__step-status--ok'
    }
    // The model's `thought` argument explains the step in plain words.
    const summary = (event) =>
      typeof event.args?.thought === 'string' ? event.args.thought.trim() : ''
    const actions = (event) =>
      getToolActions({
        toolName: event.tool_name,
        args: event.args,
        result: event.result,
        applications: props.applications,
        t,
      })
    return {
      summary,
      actions,
      expanded,
      toggle,
      expandedResults,
      toggleResult,
      stepIcon,
      stepStatusClass,
      formatToolPayload,
    }
  },
})
</script>
