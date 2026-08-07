<template>
  <form @submit.prevent>
    <div class="ai-onboarding-questions__progress">
      {{
        $t('aiDatabaseOnboardingForm.progress', {
          current: phaseIndex + 1,
          total: phases.length,
        })
      }}
    </div>
    <p class="ai-onboarding-questions__explanation">
      {{ $t('aiDatabaseOnboardingForm.explanation') }}
    </p>
    <FormGroup
      :label="$t(`aiDatabaseOnboardingForm.${phase}Label`)"
      :helper-text="$t(`aiDatabaseOnboardingForm.${phase}Description`)"
      small-label
      required
    >
      <FormInput
        ref="input"
        v-model="values[phase]"
        :placeholder="$t(`aiDatabaseOnboardingForm.${phase}Placeholder`)"
        :maxlength="48"
        size="large"
        @input="updateValue()"
        @keydown.enter.prevent="continueOnEnter()"
      />
    </FormGroup>
  </form>
</template>

<script>
export default {
  name: 'AIDatabaseOnboardingForm',
  emits: ['input', 'next-step'],
  data() {
    return {
      phases: ['industry', 'team'],
      phaseIndex: 0,
      values: {
        industry: '',
        team: '',
      },
    }
  },
  computed: {
    phase() {
      return this.phases[this.phaseIndex]
    },
  },
  mounted() {
    this.focus()
    this.updateValue()
  },
  methods: {
    beforeNext() {
      if (this.phaseIndex >= this.phases.length - 1) {
        return false
      }
      this.goToPhase(this.phaseIndex + 1)
      return true
    },
    canGoBack() {
      return this.phaseIndex > 0
    },
    goBack() {
      this.goToPhase(this.phaseIndex - 1)
    },
    goToPhase(index) {
      this.phaseIndex = index
      this.focus()
      this.updateValue()
    },
    continueOnEnter() {
      if (this.isValid() && !this.beforeNext()) {
        this.$emit('next-step')
      }
    },
    focus() {
      this.$nextTick(() => {
        this.$refs.input?.focus()
      })
    },
    isValid() {
      return this.values[this.phase].trim() !== ''
    },
    updateValue() {
      this.$nextTick(() => {
        this.$emit('input', this.values)
      })
    },
  },
}
</script>
