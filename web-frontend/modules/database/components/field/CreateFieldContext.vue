<template>
  <Context
    ref="context"
    class="field-context"
    max-height-if-outside-viewport
    @shown="onClick"
    @hidden="onHidden"
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
  emits: ['field-created', 'field-created-callback-done', 'shown'],
  data() {
    return {
      loading: false,
      showDescription: false,
      // The field a failed save left behind, with the group its creation was
      // part of. A retry saves what is left of it rather than a second field.
      createdField: null,
      createdActionGroupId: null,
      defaultValues: {
        name: '',
        type: this.forcedType || '',
        description: null,
      },
    }
  },
  methods: {
    async submit(values) {
      if (this.createdField !== null) {
        return await this.retry(values)
      }
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

        // The field has an id now, so its actions can be saved. A failure here
        // must not roll the field back, so it is only surfaced.
        let actionsSaved = true
        try {
          await this.$refs.form.afterFieldSaved(newField.id)
        } catch (error) {
          actionsSaved = false
          notifyIf(error, 'field')
        }
        if (!actionsSaved) {
          this.createdField = newField
          this.createdActionGroupId = undoRedoActionGroupId
          // The form checks its name against the table's fields, which now
          // include this one, so a retry would clash with itself.
          this.defaultValues.id = newField.id
        }
        // Read after the save, so it reflects what actually persisted.
        const valuesAfterSave = this.$refs.form.fieldValuesAfterSave()

        const callback = async () => {
          await forceCreateCallback()
          // Only once the response is committed, since it carries a
          // `has_workflow_actions` computed before the actions existed.
          if (valuesAfterSave !== null) {
            await this.$store.dispatch('field/setItemValues', {
              id: newField.id,
              values: valuesAfterSave,
            })
          }
          this.loading = false
          // Closing would discard the edits that did not make it, with only a
          // toast to say so. The editor stays open on them to be retried.
          if (!actionsSaved) {
            return
          }
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
    /**
     * Saves what a failed create left behind. The field itself was made, so its
     * values are patched and the actions saved against it, rather than making a
     * second field.
     */
    async retry(values) {
      this.loading = true
      const field = this.createdField
      const type = values.type
      delete values.type

      try {
        // Committed right away: the field is already in the store, so there is
        // no creation left for the parent to sequence a row refresh against.
        await this.$store.dispatch('field/update', { field, type, values })

        let actionsSaved = true
        try {
          await this.$refs.form.afterFieldSaved(field.id)
        } catch (error) {
          actionsSaved = false
          notifyIf(error, 'field')
        }
        // Read after the save, so it reflects what actually persisted.
        const valuesAfterSave = this.$refs.form.fieldValuesAfterSave()
        if (valuesAfterSave !== null) {
          await this.$store.dispatch('field/setItemValues', {
            id: field.id,
            values: valuesAfterSave,
          })
        }
        this.loading = false
        if (!actionsSaved) {
          return
        }
        this.$refs.form.reset()
        this.hide()
      } catch (error) {
        this.loading = false
        if (!this.$refs.form.handleErrorByForm(error)) {
          notifyIf(error, 'field')
        }
      }
    },
    /**
     * A retry that is abandoned still made a field, so the view is told about
     * it and the next open starts a new one.
     */
    onHidden() {
      if (this.createdField === null) {
        return
      }
      const newField = this.createdField
      const undoRedoActionGroupId = this.createdActionGroupId
      this.createdField = null
      this.createdActionGroupId = null
      delete this.defaultValues.id
      this.$refs.form.reset()
      this.$emit('field-created-callback-done', {
        newField,
        undoRedoActionGroupId,
      })
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
    onClick($event) {
      this.onShow()
      this.$emit('shown', $event)
    },
    handleFileTypeChanged(event) {},
  },
}
</script>
