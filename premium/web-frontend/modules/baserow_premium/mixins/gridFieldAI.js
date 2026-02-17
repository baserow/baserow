import { notifyIf } from '@baserow/modules/core/utils/error'

import FieldService from '@baserow_premium/services/field'
import { AI_FIELD_STATUS } from '@baserow_premium/constants'
import { getAIFieldStatus } from '@baserow_premium/utils/ai'

/**
 * Check if the AI model is available for a given field.
 */
function checkIsModelAvailable(store, registry, workspaceId, field) {
  const workspace = store.getters['workspace/get'](workspaceId)
  if (!workspace) return false

  const aIModels =
    workspace.generative_ai_models_enabled[field.ai_generative_ai_type] || []
  return (
    registry.get('field', field.type).isEnabled(workspace) &&
    aIModels.includes(field.ai_generative_ai_model)
  )
}

export default {
  computed: {
    generating() {
      return (
        getAIFieldStatus(this.row, this.field.id) === AI_FIELD_STATUS.GENERATING
      )
    },
    generationError() {
      if (getAIFieldStatus(this.row, this.field.id) === AI_FIELD_STATUS.ERROR) {
        return {
          message: this.$t('gridViewFieldAI.generationFailed'),
        }
      }
      return null
    },
    metadataStatusIndicator() {
      if (getAIFieldStatus(this.row, this.field.id) === AI_FIELD_STATUS.ERROR) {
        return {
          icon: 'iconoir-warning-triangle',
          color: 'var(--color-warning)',
          message: this.$t('gridViewFieldAI.generationFailed'),
        }
      }
      return null
    },
    modelAvailable() {
      return checkIsModelAvailable(
        this.$store,
        this.$registry,
        this.workspaceId,
        this.field
      )
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
      return (
        getAIFieldStatus(parent.row, props.field.id) ===
        AI_FIELD_STATUS.GENERATING
      )
    },
    isModelAvailable(parent, props) {
      return checkIsModelAvailable(
        parent.$store,
        parent.$registry,
        props.workspaceId,
        props.field
      )
    },
    async generate() {
      if (this.isDeactivated) {
        this.$refs.clickModal.show()
        return
      }

      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/grid/generateAIFieldValue',
          {
            fieldId: this.field.id,
            rowId: this.row.id,
            generateFn: (fId, rId) =>
              FieldService(this.$client).generateAIFieldValues(fId, [rId]),
          }
        )
      } catch (error) {
        notifyIf(error, 'field')
      }
    },
  },
}
