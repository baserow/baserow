<template>
  <Context
    ref="context"
    class="field-context"
    max-height-if-outside-viewport
    @shown="
      onShow()
      $emit('shown', $event)
    "
  >
    <div class="field-context__content">
      <FieldForm
        ref="form"
        :table="table"
        :view="view"
        :forced-type="forcedType"
        :all-fields-in-table="allFieldsInTable"
        :default-values="defaultValues"
        :database="database"
        @submitted="submit"
        @keydown-enter="$refs.submitButton.focus()"
        @field-type-changed="handleFileTypeChanged"
      />

      <div
        class="context__footer context__form-footer-actions--multiple-actions"
      >
        <span class="context__form-footer-actions--alight-left">
          <ButtonText
            v-if="!showDescription"
            ref="showDescription"
            tag="a"
            class="button-text--no-underline"
            icon="iconoir-plus"
            type="secondary"
            @click="showDescriptionField"
          >
            {{ $t('fieldForm.addDescription') }}
          </ButtonText>
        </span>
        <Button
          ref="submitButton"
          type="primary"
          :loading="loading"
          :disabled="loading"
          @click="$refs.form.submit()"
        >
          {{ $t('action.create') }}
        </Button>
      </div>
    </div>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'
import FieldForm from '@baserow/modules/database/components/field/FieldForm'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { createNewUndoRedoActionGroupId } from '@baserow/modules/database/utils/action'

export default {
  name: 'CreateFieldContext',
  components: { FieldForm },
  mixins: [context],
  props: {
    table: {
      type: Object,
      required: true,
    },
    view: {
      type: Object,
      required: true,
    },
    forcedType: {
      type: [String, null],
      required: false,
      default: null,
    },
    allFieldsInTable: {
      type: Array,
      required: true,
    },
    database: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      loading: false,
      showDescription: false,
      defaultValues: {
        name: '',
        type: this.forcedType || '',
        description: null,
      },
    }
  },
  methods: {
    async submit(values) {
      this.loading = true

      const type = values.type
      delete values.type
      const actionGroupId = createNewUndoRedoActionGroupId()
      try {
        const {
          forceCreateCallback,
          fetchNeeded,
          newField,
          undoRedoActionGroupId,
        } = await this.$store.dispatch('field/create', {
          type,
          values,
          table: this.table,
          forceCreate: false,
          undoRedoActionGroupId: actionGroupId,
        })
        const callback = async () => {
          await forceCreateCallback()
          this.createdId = null
          this.loading = false
          this.$refs.form.reset()
          this.hide()
          this.$emit('field-created-callback-done', {
            newField,
            undoRedoActionGroupId,
          })
        }
        this.$emit('field-created', { callback, newField, fetchNeeded })
      } catch (error) {
        this.loading = false
        const handledByForm = this.$refs.form.handleErrorByForm(error)
        if (!handledByForm) {
          notifyIf(error, 'field')
        }
      }
    },
    showFieldTypesDropdown(target) {
      this.$refs.form.showFieldTypesDropdown(target)
    },
    showDescriptionField(evt) {
      this.hideDescriptionLink()
      this.$refs.form.showDescriptionField()
      evt.stopPropagation()
      evt.preventDefault()
    },
    hideDescriptionLink() {
      this.showDescription = true
    },
    onShow() {
      this.showDescription = this.$refs.form.isDescriptionFieldNotEmpty()
    },
    handleFileTypeChanged(event) {},
  },
}
</script>
