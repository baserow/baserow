<template>
  <div class="assistant__context-badge">
    <i v-if="contextIcon" :class="['assistant__context-icon', contextIcon]"></i>
    <span class="assistant__context-text">{{ contextDisplay }}</span>
  </div>
</template>

<script>
export default {
  name: 'AssistantUiContext',
  props: {
    uiContext: {
      type: Object,
      default: () => ({}),
    },
  },
  computed: {
    contextIcon() {
      const applicationType = this.uiContext.applicationType
      if (!applicationType) {
        return null
      }

      return this.$registry.get('application', applicationType).getIconClass()
    },
    contextDisplay() {
      if (this.uiContext.view) {
        return this.uiContext.table.name + ' - ' + this.uiContext.view.name
      } else if (this.uiContext.table) {
        return this.uiContext.table.name
      } else if (this.uiContext.workflow) {
        return this.uiContext.workflow.name
      } else if (this.uiContext.application) {
        return this.uiContext.application.name
      } else if (this.uiContext.workspace) {
        return this.uiContext.workspace.name
      }
      return ''
    },
  },
}
</script>
