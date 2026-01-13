<template>
  <a
    class="context__menu-item-link"
    :class="{
      'context__menu-item-link--loading': duplicating,
      disabled: disabled || duplicating,
    }"
    @click="duplicateTable()"
  >
    <i class="context__menu-item-icon iconoir-copy"></i>
    {{ $t('action.duplicate') }}
  </a>
</template>

<script>
import { notifyIf } from '@baserow/modules/core/utils/error'
import TableService from '@baserow/modules/database/services/table'

export default {
  name: 'SidebarDuplicateTableContextItem',
  props: {
    database: {
      type: Object,
      required: true,
    },
    table: {
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
    async duplicateTable() {
      if (this.duplicating || this.disabled) {
        return
      }

      this.duplicating = true
      try {
        const { data: job } = await TableService(this.$client).asyncDuplicate(
          this.table.id
        )
        this.job = job
        this.$store.dispatch('job/create', job)
      } catch (error) {
        notifyIf(error, 'table')
      }
      this.$emit('click')
    },
  },
}
</script>
