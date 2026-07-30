import { notifyIf } from '@baserow/modules/core/utils/error'

import FieldService from '@baserow_premium/services/field'
import { setAIFieldErrorFromGenerationError } from '@baserow_premium/utils/aiField'

export default {
  data() {
    return {
      generating: false,
    }
  },
  computed: {
    workspace() {
      return this.$store.getters['workspace/get'](this.workspaceId)
    },
    modelAvailable() {
      if (!this.workspace) {
        return false
      }

      const aIModels =
        this.workspace.generative_ai_models_enabled?.[
          this.field.ai_generative_ai_type
        ] || []
      return (
        this.$registry
          .get('field', this.field.type)
          .isEnabled(this.workspace) &&
        aIModels.includes(this.field.ai_generative_ai_model)
      )
    },
    isDeactivated() {
      return this.$registry
        .get('field', this.field.type)
        .isDeactivated(this.workspaceId)
    },
    fieldError() {
      return this.field.error || null
    },
    fieldHasError() {
      return !!this.fieldError
    },
    deactivatedClickComponent() {
      return this.$registry
        .get('field', this.field.type)
        .getDeactivatedClickModal(this.workspaceId)
    },
  },
  watch: {
    value() {
      this.generating = false
    },
  },
  methods: {
    async generate() {
      // Guard every caller and not just the disabled button.
      if (!this.modelAvailable || this.generating || this.fieldHasError) {
        return
      }

      this.generating = true
      try {
        await FieldService(this.$client).generateAIFieldValues(this.field.id, [
          this.$parent.row.id,
        ])
      } catch (error) {
        setAIFieldErrorFromGenerationError(this.$store, this.field, error)
        notifyIf(error, 'field')
        this.generating = false
      }
    },
  },
}
