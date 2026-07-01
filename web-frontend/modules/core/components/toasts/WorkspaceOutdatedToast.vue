<template>
  <Toast type="warning" icon="iconoir-warning-circle">
    <template #title>{{ $t('workspaceOutdatedToast.title') }}</template>
    <span>{{ $t('workspaceOutdatedToast.content') }}</span>
    <template #actions>
      <button
        class="toast__actions-button toast__actions-button--primary"
        :class="{ 'toast__actions-button--loading': loading }"
        @click="refresh()"
      >
        {{ $t('workspaceOutdatedToast.action') }}
      </button>
      <button class="toast__actions-button" @click="dismiss()">
        {{ $t('workspaceOutdatedToast.dismiss') }}
      </button>
    </template>
  </Toast>
</template>

<script>
import Toast from '@baserow/modules/core/components/toasts/Toast'

export default {
  name: 'WorkspaceOutdatedToast',
  components: {
    Toast,
  },
  data() {
    return {
      loading: false,
    }
  },
  methods: {
    refresh() {
      this.loading = true
      window.location.reload()
    },
    dismiss() {
      this.$store.dispatch('toast/setWorkspaceOutdated', false)
    },
  },
}
</script>
