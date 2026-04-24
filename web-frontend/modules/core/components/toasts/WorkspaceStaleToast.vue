<template>
  <Toast type="warning" icon="iconoir-warning-circle">
    <template #title>{{ $t('workspaceStaleToast.title') }}</template>
    <span>{{ $t('workspaceStaleToast.content') }}</span>
    <template #actions>
      <button
        class="toast__actions-button toast__actions-button--primary"
        :class="{ 'toast__actions-button--loading': loading }"
        @click="refresh()"
      >
        {{ $t('workspaceStaleToast.action') }}
      </button>
      <button class="toast__actions-button" @click="dismiss()">
        {{ $t('workspaceStaleToast.dismiss') }}
      </button>
    </template>
  </Toast>
</template>

<script>
import Toast from '@baserow/modules/core/components/toasts/Toast'

export default {
  name: 'WorkspaceStaleToast',
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
      this.$store.dispatch('toast/setWorkspaceStale', false)
    },
  },
}
</script>
