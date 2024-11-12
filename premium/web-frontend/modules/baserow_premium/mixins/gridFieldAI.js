import { notifyIf } from '@baserow/modules/core/utils/error'

import FieldService from '@baserow_premium/services/field'

export default {
  computed: {
    // Indicates if the cell is currently being generated together with other cells in
    // bulk via the apposite grid-view menu.
    generating() {
      return this.isGenerating(this.$parent, this.$props)
    },
    modelAvailable() {
      return this.isModelAvailable(this.$parent, this.$props)
    },
    isDeactivated() {
      return this.$registry
        .get('field', this.field.type)
        .isDeactivated(this.workspaceId)
    },
    deactivatedClickComponent() {
      return this.$registry
        .get('field', this.field.type)
        .getDeactivatedClickModal(this.workspaceId)
    },
    workspace() {
      return this.$store.getters['workspace/get'](this.workspaceId)
    },
  },
  methods: {
    isGenerating(parent, props) {
      // If no storePrefix is provided, then the cell is rendered outside of the
      // grid view where it can't have a generating state.
      if (!props.storePrefix) {
        return false
      }

      return parent.$store.getters[
        props.storePrefix + 'view/grid/hasPendingFieldOps'
      ](props.field.id, parent.row.id)
    },
    isModelAvailable(parent, props) {
      const workspace = parent.$store.getters['workspace/get'](
        props.workspaceId
      )
      if (!workspace) return false

      const aIModels =
        workspace.generative_ai_models_enabled[
          props.field.ai_generative_ai_type
        ] || []
      return (
        parent.$registry.get('field', props.field.type).isEnabled(workspace) &&
        aIModels.includes(props.field.ai_generative_ai_model)
      )
    },
    async generate() {
      if (this.isDeactivated) {
        this.$refs.clickModal.show()
        return
      }

      const rowId = this.$parent.row.id
      this.$store.dispatch(
        this.storePrefix + 'view/grid/setPendingFieldOperations',
        { fieldId: this.field.id, rowIds: [rowId], value: true }
      )
      try {
        await FieldService(this.$client).generateAIFieldValues(this.field.id, [
          rowId,
        ])
      } catch (error) {
        notifyIf(error, 'field')
        this.$store.dispatch(
          this.storePrefix + 'view/grid/setPendingFieldOperations',
          { fieldId: this.field.id, rowIds: [rowId], value: false }
        )
      }
    },
  },
}
