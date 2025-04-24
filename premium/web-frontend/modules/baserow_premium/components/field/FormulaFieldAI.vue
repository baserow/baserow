<template>
  <div class="margin-top-1">
    <a v-if="hasPremium" @click="$refs.aiModal.show()">
      <i class="iconoir-magic-wand"></i>
      {{ $t('formulaFieldAI.generateWithAI') }}
    </a>
    <a v-else @click="$refs.paidFeaturesModal.show()">
      <i class="iconoir-lock"></i>
      {{ $t('formulaFieldAI.generateWithAI') }}
    </a>
    <AIFormulaModal
      ref="aiModal"
      :database="database"
      :table="table"
      @formula="$emit('update-formula', $event)"
    ></AIFormulaModal>
    <PaidFeaturesModal
      ref="paidFeaturesModal"
      :workspace="workspace"
      initial-selected-type="ai_features"
    ></PaidFeaturesModal>
  </div>
</template>

<script>
import AIFormulaModal from '@baserow_premium/components/field/AIFormulaModal'
import PremiumFeatures from '@baserow_premium/features'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'

export default {
  name: 'FormulaFieldAI',
  components: { PaidFeaturesModal, AIFormulaModal },
  props: {
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
  },
  computed: {
    hasPremium() {
      return this.$hasFeature(
        PremiumFeatures.PREMIUM,
        this.database.workspace.id
      )
    },
    workspace() {
      return this.$store.getters['workspace/get'](this.database.workspace.id)
    },
  },
}
</script>
