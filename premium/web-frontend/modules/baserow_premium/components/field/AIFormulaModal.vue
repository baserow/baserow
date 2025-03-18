<template>
  <Modal ref="modal" small>
    <template #content>
      <div class="box__title">
        <h2 class="row_modal__title">{{ $t('aiFormulaModal.title') }}</h2>
      </div>
      <Error :error="error"></Error>
      <template v-if="hasModels">
        <p>
          {{ $t('aiFormulaModal.description') }}
        </p>
        <AIFormulaForm :database="database" @submitted="submit">
          <Button type="primary" :loading="loading" :disabled="loading">{{
            $t('aiFormulaModal.generate')
          }}</Button>
        </AIFormulaForm>
      </template>
      <p v-else>
        {{ $t('aiFormulaModal.noModels') }}
      </p>
    </template>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import FieldService from '@baserow_premium/services/field'
import AIFormulaForm from '@baserow_premium/components/field/AIFormulaForm.vue'

export default {
  name: 'AIFormulaModal',
  components: { AIFormulaForm },
  mixins: [modal, error],
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
  data() {
    return {
      loading: false,
    }
  },
  computed: {
    // Return the reactive object that can be updated in runtime.
    workspace() {
      return this.$store.getters['workspace/get'](this.database.workspace.id)
    },
    hasModels() {
      return Object.values(this.workspace.generative_ai_models_enabled).some(
        (models) => models.length > 0
      )
    },
  },
  methods: {
    async submit(values) {
      if (this.loading) {
        return
      }

      this.loading = true

      try {
        const { data } = await FieldService(this.$client).generateAIFormula(
          this.table.id,
          values.ai_generative_ai_type,
          values.ai_generative_ai_model,
          values.ai_temperature || null,
          values.ai_prompt
        )
        this.$emit('formula', data.formula)
        this.hide()
      } catch (error) {
        this.handleError(error)
      } finally {
        this.loading = false
      }
    },
  },
}
</script>
