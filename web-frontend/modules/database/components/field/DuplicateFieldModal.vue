<template>
  <Modal :tiny="true" @show="hideError()">
    <h2 class="box__title">
      {{ $t('duplicateFieldContext.duplicate') }}
    </h2>
    <Error :error="error"></Error>
    <form @submit.prevent="duplicateField()">
      <div class="control margin-bottom-1">
        <div class="control__elements">
          <Checkbox v-model="duplicateData" :disabled="formFieldTypeIsReadOnly">
            {{
              $t(
                formFieldTypeIsReadOnly
                  ? 'duplicateFieldContext.readOnlyField'
                  : 'duplicateFieldContext.cloneData'
              )
            }}
          </Checkbox>
        </div>
      </div>
      <div class="actions actions--right">
        <Button
          ref="submitButton"
          type="primary"
          :loading="loading"
          :disabled="loading"
        >
          {{ $t('action.duplicate') }}
        </Button>
      </div>
    </form>
  </Modal>
</template>

<script>
import { notifyIf } from '@baserow/modules/core/utils/error'
import { createNewUndoRedoActionGroupId } from '@baserow/modules/database/utils/action'
import FieldService from '@baserow/modules/database/services/field'
import jobProgress from '@baserow/modules/core/mixins/jobProgress'
import error from '@baserow/modules/core/mixins/error'
import modal from '@baserow/modules/core/mixins/modal'

export default {
  name: 'DuplicateFieldModal',
  mixins: [modal, error, jobProgress],
  props: {
    table: {
      type: Object,
      required: true,
    },
    fromField: {
      type: Object,
      required: true,
    },
    allFieldsInTable: {
      type: Array,
      required: true,
    },
  },
  data() {
    return {
      loading: false,
      duplicateData: true,
      actionGroupId: null,
    }
  },
  computed: {
    existingFieldName() {
      return this.allFieldsInTable.map((field) => field.name)
    },
    formFieldTypeIsReadOnly() {
      const fieldType = this.$registry.get('field', this.fromField.type)
      return fieldType.isReadOnlyField(this.fromField)
    },
  },
  methods: {
    onDuplicationEnd() {
      this.loading = false
      this.actionGroupId = null
    },
    showError(title, message) {
      this.$store.dispatch('toast/error', { title, message }, { root: true })
    },
    // eslint-disable-next-line require-await
    async onJobFailed() {
      this.onDuplicationEnd()
      this.showError(
        this.$t('clientHandler.notCompletedTitle'),
        this.$t('clientHandler.notCompletedDescription')
      )
    },
    // eslint-disable-next-line require-await
    async onJobPollingError(error) {
      this.onDuplicationEnd()
      notifyIf(error, 'table')
    },
    async onJobDone() {
      const newFieldId = this.job.duplicated_field.id
      try {
        const { data: newField } = await FieldService(this.$client).get(
          newFieldId
        )
        this.onFieldDuplicated(newField)
      } catch (error) {
        this.onDuplicationEnd()
        notifyIf(error, 'table')
      }
    },
    onFieldDuplicated(newField) {
      try {
        const callback = async () => {
          await this.$store.dispatch('field/forceCreate', {
            table: this.table,
            values: newField,
            relatedFields: newField.related_fields,
          })
          this.hide()
          // GridViewHead will update the order of the fields
          this.$emit('move-field', {
            newField,
            position: 'right',
            fromField: this.fromField,
            undoRedoActionGroupId: this.actionGroupId,
          })
          this.onDuplicationEnd()
        }
        this.$emit('field-created', { callback, newField, fetchNeeded: true })
      } catch (error) {
        this.onDuplicationEnd()
        this.handleError(error)
      }
    },
    async duplicateField() {
      if (this.loading || this.disabled) {
        return
      }
      this.loading = true
      this.hideError()
      this.actionGroupId = createNewUndoRedoActionGroupId()
      try {
        const { data: job } = await FieldService(this.$client).asyncDuplicate(
          this.fromField.id,
          this.duplicateData,
          this.actionGroupId
        )
        this.startJobPoller(job)
      } catch (error) {
        this.onDuplicationEnd()
        notifyIf(error, 'table')
      }
    },
  },
}
</script>
