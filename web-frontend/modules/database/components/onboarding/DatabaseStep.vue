<template>
  <div>
    <h1>{{ $t('databaseStep.title') }}</h1>
    <p>
      {{ $t('databaseStep.description') }}
    </p>
    <div class="margin-bottom-2">
      <SegmentControl
        v-model:active-index="selectedTypeIndex"
        :segments="types"
        :initial-active-index="0"
        @update:active-index="updateValue"
      ></SegmentControl>
    </div>
    <template v-if="hasName">
      <FormGroup
        :error="v$.name.$error"
        :label="$t('databaseStep.databaseNameLabel')"
        small-label
        required
      >
        <FormInput
          ref="nameInput"
          v-model="name"
          :placeholder="$t('databaseStep.databaseNameLabel')"
          :label="$t('databaseStep.databaseNameLabel')"
          size="large"
          :error="v$.name.$error"
          @input=";[v$.name.$touch(), updateValue()]"
        />
        <template #error>{{ v$.name.$errors[0].$message }}</template>
      </FormGroup>
    </template>
    <component
      :is="selectedStepType.getComponent()"
      v-if="selectedStepType.getComponent()"
      ref="stepComponent"
      @input="updateValue($event)"
      @selected-template="selectedTemplate"
    ></component>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required, helpers } from '@vuelidate/validators'
import { useI18n } from 'vue-i18n'
import { DatabaseOnboardingType } from '@baserow/modules/database/onboardingTypes'

export default {
  name: 'DatabaseStep',
  props: {
    data: {
      required: true,
      type: Object,
    },
  },
  emits: ['update-data'],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    const { t } = useI18n()
    const name = this.$store.getters['auth/getName']

    return {
      selectedTypeIndex: 0,
      name: t('databaseStep.databaseNamePrefill', { name }),
    }
  },
  computed: {
    allStepTypes() {
      return this.$registry.getOrderedList('databaseOnboardingStep')
    },
    visibleTypes() {
      return this.allStepTypes
        .filter((stepType) => stepType.isVisible())
        .map((stepType) => ({
          type: stepType.getType(),
          label: stepType.getLabel(),
        }))
    },
    types() {
      return this.visibleTypes
    },
    selectedType() {
      return this.visibleTypes[this.selectedTypeIndex].type
    },
    selectedStepType() {
      return this.allStepTypes.find(
        (stepType) => stepType.getType() === this.selectedType
      )
    },
    hasName() {
      return this.selectedStepType.hasNameInput()
    },
  },
  watch: {
    hasName: {
      immediate: true,
      handler(newValue) {
        if (newValue) {
          this.$nextTick(() => {
            if (this.$refs.nameInput) {
              this.$refs.nameInput.focus()
              this.v$.name.$touch()
            }
          })
        }
      },
    },
  },
  mounted() {
    this.updateValue()
  },
  methods: {
    isValid() {
      return this.selectedStepType.isValid(this.data, this.v$, this.$refs)
    },
    updateValue(params = {}) {
      this.$nextTick(() => {
        this.$emit('update-data', {
          name: this.name,
          type: this.selectedType,
          ...params,
        })
      })
    },
    selectedTemplate(template) {
      this.$nextTick(() => {
        this.$emit('update-data', {
          type: this.selectedType,
          template,
        })
      })
    },
  },
  validations() {
    const rules = {}
    if (this.hasName) {
      rules.name = {
        required: helpers.withMessage(this.$t('error.requiredField'), required),
      }
    }
    return rules
  },
}
</script>
