<template>
  <Modal ref="modal" :small="true">
    <h2 class="box__title">{{ $t('aiOnboardingDetailsModal.title') }}</h2>
    <form @submit.prevent="submit">
      <FormGroup
        v-for="field in fields"
        :key="field"
        :label="$t(`aiDatabaseOnboardingForm.${field}Label`)"
        :helper-text="$t(`aiDatabaseOnboardingForm.${field}Description`)"
        small-label
        required
        class="margin-bottom-2"
      >
        <FormInput
          v-model="values[field]"
          :placeholder="$t(`aiDatabaseOnboardingForm.${field}Placeholder`)"
          :maxlength="48"
          size="large"
        />
      </FormGroup>
      <div class="actions actions--right">
        <Button type="primary" size="large" :disabled="!isValid">{{
          $t('aiOnboardingDetailsModal.submit')
        }}</Button>
      </div>
    </form>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'

export default {
  name: 'AIOnboardingDetailsModal',
  mixins: [modal],
  props: {
    industry: { type: String, required: true },
    team: { type: String, required: true },
  },
  emits: ['updated'],
  data() {
    return {
      fields: ['industry', 'team'],
      values: {
        industry: '',
        team: '',
      },
    }
  },
  computed: {
    isValid() {
      return this.fields.every((field) => this.values[field].trim() !== '')
    },
  },
  methods: {
    show(...args) {
      this.fields.forEach((field) => {
        this.values[field] = this[field]
      })
      this.$refs.modal.show(...args)
    },
    submit() {
      if (this.isValid) {
        this.$emit('updated', { ...this.values })
        this.hide()
      }
    },
  },
}
</script>
