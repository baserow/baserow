<template>
  <Context overflow-scroll max-height-if-outside-viewport>
    <div class="timeline-date-settings-form">
      <TimelineDateSettingsForm
        ref="datesSettingsForm"
        :fields="fields"
        :view="view"
        :read-only="readOnly"
        @submitted="submitted"
      >
        <div v-if="!readOnly" class="actions actions--right">
          <Button type="primary" :loading="loading" :disabled="loading">
            {{ $t('selectDateFieldContext.save') }}</Button
          >
        </div>
      </TimelineDateSettingsForm>
    </div>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'
import { notifyIf } from '@baserow/modules/core/utils/error'
import TimelineDateSettingsForm from '@baserow_premium/components/views/timeline/TimelineDateSettingsForm'

export default {
  name: 'TimelineDateSettingsHeaderContext',
  components: {
    TimelineDateSettingsForm,
  },
  mixins: [context],
  props: {
    view: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
  },
  data() {
    return {
      loading: false,
    }
  },
  methods: {
    async submitted(values) {
      this.loading = true
      const view = this.view
      this.$store.dispatch('view/setItemLoading', { view, value: true })
      try {
        await this.$store.dispatch('view/update', {
          view,
          values: {
            start_date_field: values.startDateFieldId,
            end_date_field: values.endDateFieldId,
          },
        })
        this.$emit('refresh', {
          includeFieldOptions: true,
        })
        this.hide()
      } catch (error) {
        notifyIf(error, 'view')
      } finally {
        this.loading = false
        this.$store.dispatch('view/setItemLoading', { view, value: false })
      }
    },
  },
}
</script>
