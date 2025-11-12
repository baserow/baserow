<template>
  <li v-if="isAIField" class="context__menu-item">
    <a
      class="context__menu-item-link"
      :class="{
        disabled: !modelAvailable,
      }"
      @click.prevent.stop="openModal()"
    >
      <i class="context__menu-item-icon iconoir-magic-wand"></i>
      {{ $t('gridView.generateAllAiValues') }}
      <div v-if="!hasPremium" class="deactivated-label">
        <i class="iconoir-lock"></i>
      </div>
    </a>
    <PaidFeaturesModal
      ref="paidFeaturesModal"
      :workspace="database.workspace"
      :initial-selected-type="featureName"
    />
    <GenerateAIValuesModal
      ref="generateAIValuesModal"
      :database="database"
      :table="table"
      :field="field"
      :view="view"
    />
  </li>
</template>

<script>
import PremiumFeatures from '@baserow_premium/features'
import GenerateAIValuesModal from '@baserow_premium/components/field/GenerateAIValuesModal'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import { AIPaidFeature } from '@baserow_premium/paidFeatures'

export default {
  name: 'GenerateAIValuesContextItem',
  components: {
    GenerateAIValuesModal,
    PaidFeaturesModal,
  },
  props: {
    field: {
      type: Object,
      required: true,
    },
    view: {
      type: Object,
      required: false,
      default: null,
    },
    table: {
      type: Object,
      required: true,
    },
    database: {
      type: Object,
      required: true,
    },
  },
  computed: {
    featureName() {
      return AIPaidFeature.getType()
    },
    isAIField() {
      return this.field.type === 'ai'
    },
    workspace() {
      return this.$store.getters['workspace/get'](this.database.workspace.id)
    },
    modelAvailable() {
      if (!this.isAIField) {
        return false
      }
      const aIModels =
        this.workspace.generative_ai_models_enabled[
          this.field.ai_generative_ai_type
        ] || []
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
  },
  methods: {
    openModal() {
      if (!this.hasPremium) {
        this.$refs.paidFeaturesModal.show()
      } else if (this.modelAvailable) {
        this.$emit('hide-context')
        this.$refs.generateAIValuesModal.show()
      }
    },
  },
}
</script>
