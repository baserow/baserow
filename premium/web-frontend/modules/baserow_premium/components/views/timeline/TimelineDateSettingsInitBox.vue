<template>
  <div class="box timeline-date-settings-init-box">
    <h2 :style="{ marginBottom: '28px' }">
      {{ $t('initTimelineViewSettings.settings') }}
    </h2>
    <Error :error="error"></Error>
    <TimelineDateSettingsForm
      ref="dateSettingsForm"
      :fields="fields"
      :view="view"
      :read-only="readOnly"
      @submitted="submitted"
    >
      <div class="actions">
        <div class="align-right">
          <Button type="primary" :loading="loading" :disabled="loading">
            {{ $t('selectDateFieldModal.save') }}</Button
          >
        </div>
      </div>
    </TimelineDateSettingsForm>
  </div>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import TimelineDateSettingsForm from './TimelineDateSettingsForm'

export default {
  name: 'TimelineDateSettingsInitBox',
  components: { TimelineDateSettingsForm },
  mixins: [modal, error],
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
      this.hideError()
      const view = this.view
      this.$store.dispatch('view/setItemLoading', { view, value: true })
      try {
        await this.$store.dispatch('view/update', {
          view,
          values: {
            start_date_field: values.startDateFieldId,
            end_date_field: values.endDateFieldId,
          },
          // we want to fetch rows after this update is confirmed by the server
          optimisticUpdate: false,
        })
      } catch (error) {
        this.handleError(error)
      } finally {
        this.loading = false
        this.$store.dispatch('view/setItemLoading', { view, value: false })
      }
    },
  },
}
</script>
