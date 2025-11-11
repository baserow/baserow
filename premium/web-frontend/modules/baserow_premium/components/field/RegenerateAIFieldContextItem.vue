<template>
  <li v-if="isAIField" class="context__menu-item">
    <a
      class="context__menu-item-link"
      :class="{
        disabled: !modelAvailable || !hasPremium,
      }"
      @click.prevent.stop="openModal()"
    >
      <i class="context__menu-item-icon iconoir-magic-wand"></i>
      {{ $t('gridView.regenerateInBulk') }}
    </a>
    <RegenerateAIFieldModal
      ref="regenerateModal"
      :database="database"
      :table="table"
      :field="field"
      :view="view"
    />
  </li>
</template>

<script>
import PremiumFeatures from '@baserow_premium/features'
import RegenerateAIFieldModal from '@baserow_premium/components/field/RegenerateAIFieldModal'

export default {
  name: 'RegenerateAIFieldContextItem',
  components: {
    RegenerateAIFieldModal,
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
      if (!this.modelAvailable || !this.hasPremium) {
        return
      }

      this.$emit('hide-context')
      this.$refs.regenerateModal.show()
    },
  },
}
</script>
