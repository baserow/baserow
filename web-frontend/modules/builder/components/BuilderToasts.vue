<template>
  <div class="ab-toasts__container-top">
    <BuilderToast
      v-for="toast in toasts"
      :key="toast.id"
      :type="toast.type"
      :icon="toastIcon(toast.type)"
      close-button
      @close="closeToast(toast)"
    >
      <template #title>{{ toast.title }}</template>
      <div>{{ toast.message }}</div>
      <details v-if="toast.details" class="ab-toast__details">
        <summary class="ab-toast__details-summary">
          {{ $t('builderToast.details') }}
        </summary>
        <div class="ab-toast__details-description">
          {{ toast.details }}
        </div>
      </details>
    </BuilderToast>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'

import BuilderToast from '@baserow/modules/builder/components/BuilderToast'

export default {
  name: 'BuilderToasts',
  components: {
    BuilderToast,
  },
  computed: {
    ...mapGetters({
      toasts: 'builderToast/all',
    }),
  },
  methods: {
    toastIcon(toastType) {
      switch (toastType) {
        case 'warning':
          return 'iconoir-warning-circle'
        case 'success':
          return 'iconoir-check-circle'
        case 'info-primary':
          return 'iconoir-info-empty'
        case 'error':
          return 'iconoir-warning-triangle'
        default:
          return 'iconoir-info-empty'
      }
    },
    closeToast(toast) {
      this.$store.dispatch('builderToast/remove', toast)
    },
  },
}
</script>
