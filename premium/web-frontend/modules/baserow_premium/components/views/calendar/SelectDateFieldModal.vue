<template>
  <Modal ref="modal">
    <h2 class="box__title">
      {{ $t('selectDateFieldModal.chooseDateField') }}
    </h2>
    <Error :error="error"></Error>
    <DateFieldSelectForm
      ref="dateFieldSelectForm"
      :date-fields="dateFields"
      :date-field-id="dateFieldId"
      :table="table"
      @submitted="submitted"
    >
      <div class="actions">
        <div class="align-right">
          <Button
            type="primary"
            :loading="loading"
            :disabled="loading"
            size="large"
          >
            {{ $t('selectDateFieldModal.save') }}</Button
          >
        </div>
      </div>
    </DateFieldSelectForm>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import DateFieldSelectForm from '@baserow_premium/components/views/calendar/DateFieldSelectForm'

export default {
  name: 'SelectDateFieldModal',
  emits: ['refresh'],
  components: {
    DateFieldSelectForm,
  },
  mixins: [modal, error],
  props: {
    view: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    database: {
      type: Object,
      required: true,
    },
    dateFieldId: {
      type: Number,
      required: false,
      default: null,
    },
  },
  data() {
    return {
      loading: false,
    }
  },
  computed: {
    dateFields() {
      return this.fields.filter((f) => {
        return this.$registry.get('field', f.type).canRepresentDate(f)
      })
    },
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
          values: { date_field: values.dateFieldId },
        })
        this.$emit('refresh', {
          includeFieldOptions: true,
        })
        this.hide()
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
