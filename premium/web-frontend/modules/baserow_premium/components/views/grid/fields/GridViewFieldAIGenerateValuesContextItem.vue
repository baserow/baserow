<template>
  <li class="context__menu-item">
    <a
      v-tooltip="fieldError"
      class="context__menu-item-link"
      :class="{
        disabled: !modelAvailable || !hasPremium || fieldHasError,
        'context__menu-item-link--loading': loading,
      }"
      @click.prevent.stop="generateAIFieldValues()"
    >
      <i class="context__menu-item-icon iconoir-magic-wand"></i>
      {{ $t('gridView.generateCellsValues') }}
    </a>
  </li>
</template>

<script>
import { notifyIf } from '@baserow/modules/core/utils/error'
import FieldService from '@baserow_premium/services/field'
import PremiumFeatures from '@baserow_premium/features'
import { setAIFieldErrorFromGenerationError } from '@baserow_premium/utils/aiField'
import { getEnabledModelsForAIProviderFeature } from '@baserow/modules/core/aiProviderModelFeatureTypes'
import { FF_AI_PROVIDERS } from '@baserow/modules/core/plugins/featureFlags'

export default {
  emits: ['click'],

  props: {
    field: {
      type: Object,
      required: true,
    },
    getRows: {
      type: Function,
      required: true,
    },
    storePrefix: {
      type: String,
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
    }
  },
  computed: {
    workspace() {
      return this.$store.getters['workspace/get'](this.database.workspace.id)
    },
    modelAvailable() {
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
    hasPremium() {
      return this.$hasFeature(PremiumFeatures.PREMIUM, this.workspace.id)
    },
    fieldError() {
      return this.field.error || null
    },
    fieldHasError() {
      return !!this.fieldError
    },
  },
  methods: {
    async generateAIFieldValues($event) {
      if (!this.modelAvailable || !this.hasPremium || this.fieldHasError) {
        return
      }

      this.loading = true
      let rows = []

      try {
        rows = await this.getRows()
      } catch (error) {
        notifyIf(error, 'rows')
        return
      }

      const rowIds = rows.map((row) => row.id)
      this.loading = false

      const fieldId = this.field.id
      this.$store.dispatch(
        this.storePrefix + 'view/grid/setPendingFieldOperations',
        { fieldId, rowIds, value: true }
      )

      try {
        await FieldService(this.$client).generateAIFieldValues(fieldId, rowIds)
      } catch (error) {
        setAIFieldErrorFromGenerationError(
          this.$store,
          this.field,
          error,
          this.$t('clientHandler.modelDoesNotBelongToTypeDescription')
        )
        this.$store.dispatch(
          this.storePrefix + 'view/grid/setPendingFieldOperations',
          { fieldId, rowIds, value: false }
        )
        notifyIf(error, 'field')
      }
      this.$emit('click', $event)
    },
  },
}
</script>
