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
      // A close that arrived while a save was running. It is reported once the
      // save settles, since `@hidden` does not fire a second time.
      hidePending: false,
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
          // toast to say so. The editor stays open on them to be retried,
          // unless it was already closed while this was running.
          if (!actionsSaved) {
            this.flushPendingHide()
            return
          }
          this.hidePending = false
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
        this.flushPendingHide()
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

      const undoRedoActionGroupId = this.createdActionGroupId
      try {
        // Sent under the group the create used, or undoing the create trashes
        // the field and leaves this patch nothing to undo.
        const forceUpdateCallback = await this.$store.dispatch('field/update', {
          field,
          type,
          values,
          forceUpdate: false,
          undoRedoActionGroupId,
        })

        let actionsSaved = true
        try {
          await this.$refs.form.afterFieldSaved(field.id)
        } catch (error) {
          actionsSaved = false
          notifyIf(error, 'field')
        }
        // Read after the save, so it reflects what actually persisted.
        const valuesAfterSave = this.$refs.form.fieldValuesAfterSave()

        const callback = async () => {
          await forceUpdateCallback()
          if (valuesAfterSave !== null) {
            await this.$store.dispatch('field/setItemValues', {
              id: field.id,
              values: valuesAfterSave,
            })
          }
          this.loading = false
          if (!actionsSaved) {
            this.flushPendingHide()
            return
          }
          // Reported here rather than left to `onHidden`, which would hand the
          // parent the copy taken before this retry patched it.
          this.hidePending = false
          this.createdField = null
          this.createdActionGroupId = null
          delete this.defaultValues.id
          this.$refs.form.reset()
          this.hide()
          this.$emit('field-created-callback-done', {
            newField: this.$store.getters['field/get'](field.id) ?? field,
            undoRedoActionGroupId,
          })
        }
        // The same event the create path emits, so the parent refreshes its
        // rows before the change is committed. A retry can change the type,
        // which is when reading rows against the old column goes wrong.
        this.$emit('field-created', {
          callback,
          newField: field,
          fetchNeeded: this.$registry
            .get('field', type)
            .shouldFetchDataWhenAdded(),
        })
      } catch (error) {
        this.loading = false
        this.flushPendingHide()
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
      // A save still running reports the field itself once it settles, and
      // reporting it here as well would hand the parent two of the same
      // field. Held rather than dropped: a save whose actions then fail
      // reports nothing, and it is only then that a field is left behind. The
      // check comes first for that reason: on a first attempt there is nothing
      // to report yet, and by the time there is, `@hidden` has been and gone.
      if (this.loading) {
        this.hidePending = true
        return
      }
      if (this.createdField === null) {
        return
      }
      this.reportCreatedField()
    },
    /**
     * Hands the field a failed save left behind to the view, and forgets it so
     * the next open starts a new one.
     */
    reportCreatedField() {
      const newField = this.createdField
      const undoRedoActionGroupId = this.createdActionGroupId
      this.hidePending = false
      this.createdField = null
      this.createdActionGroupId = null
      delete this.defaultValues.id
      this.$refs.form.reset()
      this.$emit('field-created-callback-done', {
        newField,
        undoRedoActionGroupId,
      })
    },
    /**
     * Runs the close that arrived mid save, now that the save has settled.
     */
    flushPendingHide() {
      if (this.hidePending && this.createdField !== null) {
        this.reportCreatedField()
      }
      this.hidePending = false
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
      // Opened again, so a close held from an earlier save no longer applies.
      this.hidePending = false
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
