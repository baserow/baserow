<template>
  <div>
    <h1>{{ $t('databaseStep.title') }}</h1>
    <p>
      {{ $t('databaseStep.description') }}
    </p>
    <div class="margin-bottom-2">
      <SegmentControl
        v-model:active-index="selectedTypeIndex"
        :segments="visibleTypes"
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
          v-model="values.name"
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
      @next-step="$emit('next-step')"
    ></component>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required, helpers } from '@vuelidate/validators'
import { ref, reactive, computed } from 'vue'
import { useStore } from 'vuex'
import { useI18n } from 'vue-i18n'
import { useNuxtApp } from '#imports'

export default {
  name: 'DatabaseStep',
  props: {
    data: {
      required: true,
      type: Object,
    },
  },
  emits: ['update-data', 'next-step'],
  setup() {
    const { t } = useI18n()
    const { $registry } = useNuxtApp()
    const store = useStore()

    const selectedTypeIndex = ref(0)

    const allStepTypes = computed(() =>
      $registry.getOrderedList('databaseOnboardingStep')
    )
    const visibleTypes = computed(() =>
      allStepTypes.value
        .filter((stepType) => stepType.isVisible())
        .map((stepType) => ({
          type: stepType.getType(),
          label: stepType.getLabel(),
        }))
    )
    const selectedType = computed(
      () => visibleTypes.value[selectedTypeIndex.value].type
    )
    const selectedStepType = computed(() =>
      allStepTypes.value.find(
        (stepType) => stepType.getType() === selectedType.value
      )
    )
    const hasName = computed(() => selectedStepType.value.hasNameInput())

    const values = reactive({
      name: t('databaseStep.databaseNamePrefill', {
        name: store.getters['auth/getName'],
      }),
    })
    const rules = computed(() =>
      hasName.value
        ? {
            name: {
              required: helpers.withMessage(t('error.requiredField'), required),
            },
          }
        : {}
    )

    return {
      // Rules declared through the `validations()` option are only registered in
      // `onBeforeMount`, which server-side rendering never runs, leaving `v$` empty.
      v$: useVuelidate(rules, values, { $lazy: true }),
      values,
      selectedTypeIndex,
      visibleTypes,
      selectedType,
      selectedStepType,
      hasName,
    }
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
    beforeNext() {
      return this.$refs.stepComponent?.beforeNext?.() === true
    },
    canGoBack() {
      return this.$refs.stepComponent?.canGoBack?.() === true
    },
    goBack() {
      this.$refs.stepComponent.goBack()
    },
    updateValue(params = {}) {
      this.$nextTick(() => {
        this.$emit('update-data', {
          name: this.values.name,
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
}
</script>
