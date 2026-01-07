<template>
  <Context ref="context" overflow-scroll max-height-if-outside-viewport>
    <KanbanViewOptionForm
      ref="form"
      :default-values="option"
      @submitted="submit"
    >
      <div class="context__form-footer-actions">
        <Button type="primary" :loading="loading" :disabled="loading">
          {{ $t('action.save') }}</Button
        >
      </div>
    </KanbanViewOptionForm>
  </Context>
</template>

<script>
import { notifyIf } from '@baserow/modules/core/utils/error'
import context from '@baserow/modules/core/mixins/context'
import KanbanViewOptionForm from '@baserow_premium/components/views/kanban/KanbanViewOptionForm'

export default {
  name: 'KanbanViewUpdateStackContext',
  emits: ['saved'],
  components: { KanbanViewOptionForm },
  mixins: [context],
  props: {
    option: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    storePrefix: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      loading: false,
    }
  },
  methods: {
    async submit(values) {
      this.loading = true

      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/kanban/updateStack',
          {
            optionId: this.option.id,
            fields: this.fields,
            values,
          }
        )
        this.$emit('saved')
        this.hide()
      } catch (error) {
        notifyIf(error, 'field')
      }

      this.loading = false
    },
  },
}
</script>
