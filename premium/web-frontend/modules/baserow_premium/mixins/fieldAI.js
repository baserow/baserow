import { notifyIf } from '@baserow/modules/core/utils/error'
import { getEnabledModelsForAIProviderFeature } from '@baserow/modules/core/aiProviderModelFeatureTypes'
import { FF_AI_PROVIDERS } from '@baserow/modules/core/plugins/featureFlags'

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
        getEnabledModelsForAIProviderFeature(
          this.workspace,
          'ai_fields',
          this.$featureFlagIsEnabled(FF_AI_PROVIDERS)
        )[this.field.ai_generative_ai_type] || []
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
        setAIFieldErrorFromGenerationError(
          this.$store,
          this.field,
          error,
          this.$t('clientHandler.modelDoesNotBelongToTypeDescription')
        )
        notifyIf(error, 'field')
        this.generating = false
      }
    },
  },
}
