<template>
  <div v-if="isAvailable" class="assistant-prompt">
    <div class="assistant-prompt__header">
      <h4 class="assistant-prompt__title">
        {{ $t('assistantDashboardPrompt.title') }}
      </h4>
      <Badge color="cyan">{{ $t('assistantSidebarItem.title') }}</Badge>
    </div>
    <div class="assistant-prompt__field">
      <input
        v-model="prompt"
        type="text"
        class="assistant-prompt__input"
        :placeholder="$t('assistantDashboardPrompt.placeholder')"
        @keydown.enter="build()"
      />
      <Button
        type="secondary"
        size="small"
        :disabled="prompt.trim() === ''"
        @click="build()"
        >{{ $t('assistantDashboardPrompt.build') }}</Button
      >
    </div>
  </div>
</template>

<script>
import { mapActions } from 'vuex'

/**
 * Lets someone start building with the assistant straight from the workspace
 * homepage. The message is handed to the store instead of being sent here,
 * because only the panel can send it, and it mounts when the sidebar opens.
 */
export default {
  name: 'AssistantDashboardPrompt',
  props: {
    workspace: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      prompt: '',
    }
  },
  computed: {
    hasPermission() {
      return this.$hasPermission(
        'assistant.chat',
        this.workspace,
        this.workspace.id
      )
    },
    isConfigured() {
      return (
        this.workspace.ai_features?.kuma?.is_enabled ??
        !!this.$config.public.baserowEnterpriseAssistantLlmModel
      )
    },
    isAvailable() {
      return this.hasPermission && this.isConfigured
    },
  },
  methods: {
    ...mapActions({
      setPendingPrompt: 'assistant/setPendingPrompt',
    }),
    async build() {
      const message = this.prompt.trim()
      if (message === '') {
        return
      }
      this.prompt = ''
      await this.setPendingPrompt(message)
      this.$bus.$emit('toggle-right-sidebar', true)
    },
  },
}
</script>
