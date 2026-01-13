<template>
  <Context
    ref="context"
    class="field-context"
    max-height-if-outside-viewport
    @shown="onShow"
  >
    <div class="field-context__content">
      <FieldForm
        ref="form"
        :table="table"
        :view="view"
        :default-values="field"
        :primary="field.primary"
        :all-fields-in-table="allFieldsInTable"
        :database="database"
        @submitted="submit"
        @description-shown="hideDescriptionLink"
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
        <span class="context__form-footer-actions--align-right">
          <span class="margin-right-2">
            <a class="form-action" @click="cancel">{{ $t('action.cancel') }}</a>
          </span>
          <Button
            :loading="loading"
            :disabled="loading || fieldTypeDisabled"
            @click="$refs.form.submit()"
          >
            {{ $t('action.save') }}
          </Button>
        </span>
      </div>
    </div>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'
import FieldForm from '@baserow/modules/database/components/field/FieldForm'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'UpdateFieldContext',
  components: { FieldForm },
  mixins: [context],
  props: {
    table: {
      type: Object,
      required: true,
    },
    field: {
      type: Object,
      required: true,
    },
    view: {
      type: Object,
      required: true,
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
  emits: ['update', 'updated'],
  data() {
    return {
      loading: false,
      showDescription: false,
    }
  },
  computed: {
    // Return the reactive object that can be updated in runtime.
    workspace() {
      return this.$store.getters['workspace/get'](this.database.workspace.id)
    },
    fieldTypeDisabled() {
      return !this.$registry
        .get('field', this.field.type)
        .isEnabled(this.workspace)
    },
  },
  watch: {
    field() {
      // If the field values are updated via an outside source, think of real time
      // collaboration or via the modal, we want to reset the form so that it contains
      // the correct base values.
      this.reset()
    },
  },
  methods: {
    reset() {
      this.showDescription = false
      this.$nextTick(() => {
        this.$refs.form?.reset()
      })
    },
    async submit(values) {
      this.loading = true

      const type = values.type
      delete values.type

      try {
        const forceUpdateCallback = await this.$store.dispatch('field/update', {
          field: this.field,
          type,
          values,
          forceUpdate: false,
        })
        // The callback must be called as soon the parent page has refreshed the rows.
        // This is to prevent incompatible values when the field changes before the
        // actual column row has been updated. If there is nothing to refresh then the
        // callback must still be called.
        const callback = async () => {
          await forceUpdateCallback()
          this.$refs.form?.reset()
          this.loading = false
          this.hide()
          this.$emit('updated')
        }
        this.$emit('update', { callback })
      } catch (error) {
        this.loading = false
        let handledByForm = false
        if (this.$refs.form) {
          handledByForm = this.$refs.form.handleErrorByForm(error)
        }
        if (!handledByForm) {
          notifyIf(error, 'field')
        }
      }
    },
    cancel() {
      this.reset()
      this.hide()
    },
    onShow() {
      this.showDescription = this.$refs.form.isDescriptionFieldNotEmpty()
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
  },
}
</script>
