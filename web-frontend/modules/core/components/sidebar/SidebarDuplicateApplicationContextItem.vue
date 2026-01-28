<template>
  <a
    class="context__menu-item-link"
    :class="{
      'context__menu-item-link--loading': duplicating,
      disabled: disabled || duplicating,
    }"
    @click="duplicateApplication()"
  >
    <i class="context__menu-item-icon iconoir-copy"></i>
    {{
      $t('sidebarApplication.duplicate', {
        type: application._?.type?.name?.toLowerCase() || '',
      })
    }}
  </a>
</template>

<script>
import { notifyIf } from '@baserow/modules/core/utils/error'
import ApplicationService from '@baserow/modules/core/services/application'

export default {
  name: 'SidebarDuplicateApplicationContextItem',
  props: {
    application: {
      type: Object,
      required: true,
    },
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['click'],
  data() {
    return {
      duplicating: false,
      job: null,
    }
  },
  watch: {
    'job.state'(newState) {
      if (['finished', 'failed'].includes(newState)) {
        this.duplicating = false
      }
    },
  },
  methods: {
    async duplicateApplication() {
      if (this.duplicating || this.disabled) {
        return
      }

      this.duplicating = true
      try {
        const { data: job } = await ApplicationService(
          this.$client
        ).asyncDuplicate(this.application.id)
        this.job = job
        this.$store.dispatch('job/create', job)
      } catch (error) {
        this.duplicating = false
        notifyIf(error, 'application')
      } finally {
        this.$emit('click')
      }
    },
  },
}
</script>
