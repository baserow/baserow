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
      <template #title>
        <FormattedText
          :content="toast.title"
          :format="toast.titleFormat"
          preset="inline"
          :builder="builder"
          :mode="mode"
        />
      </template>
      <div>
        <FormattedText
          :content="toast.message"
          :format="toast.messageFormat"
          preset="restrictedBlock"
          :builder="builder"
          :mode="mode"
        />
      </div>
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
import FormattedText from '@baserow/modules/builder/components/FormattedText'

export default {
  name: 'BuilderToasts',
  components: {
    BuilderToast,
    FormattedText,
  },
  // Needed to resolve links in Markdown toasts. The public page provides both,
  // the editor preview only provides the builder.
  inject: {
    builder: { default: null },
    mode: { default: 'editing' },
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
