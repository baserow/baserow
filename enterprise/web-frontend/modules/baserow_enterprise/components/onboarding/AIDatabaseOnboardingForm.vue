<template>
  <form @submit.prevent="submit">
    <FormGroup
      :label="$t('aiDatabaseOnboardingForm.label')"
      :helper-text="$t('aiDatabaseOnboardingForm.description')"
      small-label
      required
    >
      <FormTextarea
        ref="promptInput"
        v-model="values.prompt"
        :placeholder="$t('aiDatabaseOnboardingForm.placeholder')"
        :rows="4"
        @input=";[v$.values.prompt.$touch(), updateValue()]"
      />
    </FormGroup>
    <div class="flex flex-wrap margin-top-2 margin-bottom-2">
      <Button
        v-for="example in examples"
        :key="example.id"
        tag="a"
        type="secondary"
        @click="setPrompt(example.prompt)"
        >{{ example.name }}</Button
      >
    </div>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import { useVuelidate } from '@vuelidate/core'
import { required } from '@vuelidate/validators'
import { useI18n } from 'vue-i18n'

export default {
  name: 'AIDatabaseOnboardingForm',
  mixins: [form],
  emits: ['input'],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  mounted() {
    this.$nextTick(() => {
      this.$refs.promptInput.focus()
    })
  },
  data() {
    const { t } = useI18n()
    return {
      values: {
        prompt: '',
      },
      examples: [
        {
          id: 'project-tracker',
          name: t('aiDatabaseOnboardingForm.exampleProjectTrackerName'),
          prompt: t('aiDatabaseOnboardingForm.exampleProjectTrackerPrompt'),
        },
        {
          id: 'product-roadmap',
          name: t('aiDatabaseOnboardingForm.exampleProductRoadmapName'),
          prompt: t('aiDatabaseOnboardingForm.exampleProductRoadmapPrompt'),
        },
        {
          id: 'company-asset-tracker',
          name: t('aiDatabaseOnboardingForm.exampleCompanyAssetTrackerName'),
          prompt: t(
            'aiDatabaseOnboardingForm.exampleCompanyAssetTrackerPrompt'
          ),
        },
        {
          id: 'team-check-ins',
          name: t('aiDatabaseOnboardingForm.exampleTeamCheckInsName'),
          prompt: t('aiDatabaseOnboardingForm.exampleTeamCheckInsPrompt'),
        },
        {
          id: 'bug-tracker',
          name: t('aiDatabaseOnboardingForm.exampleBugTrackerName'),
          prompt: t('aiDatabaseOnboardingForm.exampleBugTrackerPrompt'),
        },
      ],
    }
  },
  methods: {
    updateValue() {
      this.$nextTick(() => {
        this.$emit('input', this.values)
      })
    },
    setPrompt(prompt) {
      this.values.prompt = prompt
      this.v$.values.prompt.$touch()
      this.updateValue()
    },
  },
  validations() {
    return {
      values: {
        prompt: { required },
      },
    }
  },
}
</script>
