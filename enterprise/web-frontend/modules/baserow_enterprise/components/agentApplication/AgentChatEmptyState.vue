<template>
  <div class="agent-chat-welcome">
    <div class="agent-chat-welcome__icon">
      <i class="baserow-icon-agent"></i>
    </div>
    <h2 class="agent-chat-welcome__title">
      <i18n-t keypath="agentChat.welcomeTitle" tag="span">
        <template #name>
          <strong class="agent-chat-welcome__title-name">{{ name }}</strong>
        </template>
      </i18n-t>
    </h2>
    <p class="agent-chat-welcome__subtitle">
      {{ canRunChat ? subtitle : $t('agentChat.emptyMessageReadOnly') }}
    </p>
    <template v-if="canRunChat">
      <a
        v-for="suggestion in suggestions"
        :key="suggestion.key"
        class="agent-chat-welcome__suggestion"
        @click.prevent="suggestion.action()"
      >
        <span class="agent-chat-welcome__suggestion-icon">
          <span
            v-if="suggestion.loading"
            class="agent-chat-welcome__suggestion-spinner"
          ></span>
          <i v-else :class="suggestion.icon"></i>
        </span>
        <span class="agent-chat-welcome__suggestion-text">
          <span class="agent-chat-welcome__suggestion-title">
            {{ suggestion.title }}
          </span>
          <span class="agent-chat-welcome__suggestion-description">
            {{ suggestion.description }}
          </span>
        </span>
      </a>
    </template>
  </div>
</template>

<script>
import { defineComponent, computed } from 'vue'
import { useI18n } from '#imports'

export default defineComponent({
  name: 'AgentChatEmptyState',
  props: {
    name: {
      type: String,
      required: true,
    },
    triggerLabel: {
      type: String,
      required: false,
      default: '',
    },
    identityName: {
      type: String,
      required: false,
      default: '',
    },
    canRunChat: {
      type: Boolean,
      required: true,
    },
    canRunOnce: {
      type: Boolean,
      required: false,
      default: false,
    },
    runningOnce: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['prompt', 'run-once'],
  setup(props, { emit }) {
    const { t } = useI18n()

    const subtitle = computed(() => {
      const parts = [
        props.triggerLabel
          ? t('agentChat.welcomeRunsOn', { trigger: props.triggerLabel })
          : t('agentChat.welcomeChatOnly'),
      ]
      if (props.identityName) {
        parts.push(t('agentChat.welcomeWorksAs', { name: props.identityName }))
      }
      return parts.join(' ')
    })

    const suggestions = computed(() => {
      const items = []
      if (props.canRunOnce) {
        items.push({
          key: 'first-run',
          icon: 'iconoir-play',
          title: t('agentChat.suggestionFirstRunTitle'),
          description: t('agentChat.suggestionFirstRunDescription'),
          loading: props.runningOnce,
          action: () => {
            if (!props.runningOnce) {
              emit('run-once')
            }
          },
        })
      }
      items.push(
        {
          key: 'access',
          icon: 'iconoir-tools',
          title: t('agentChat.suggestionAccessTitle'),
          description: t('agentChat.suggestionAccessDescription'),
          action: () => emit('prompt', t('agentChat.suggestionAccessPrompt')),
        },
        {
          key: 'memory',
          icon: 'iconoir-brain',
          title: t('agentChat.suggestionMemoryTitle'),
          description: t('agentChat.suggestionMemoryDescription'),
          action: () => emit('prompt', t('agentChat.suggestionMemoryPrompt')),
        }
      )
      return items
    })

    return { subtitle, suggestions }
  },
})
</script>
