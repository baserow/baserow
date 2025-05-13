<template>
  <div class="context__form-container">
    <FormGroup
      small-label
      :label="$t('selectAIModelForm.AIType')"
      :error="fieldHasErrors('ai_generative_ai_type')"
      required
    >
      <Dropdown
        v-model="v$.values.ai_generative_ai_type.$model"
        class="dropdown--floating"
        :error="fieldHasErrors('ai_generative_ai_type')"
        :fixed-items="true"
        :show-search="false"
        @hide="v$.values.ai_generative_ai_type.$touch"
        @change="$refs.aiModel.select(aIModelsPerType[0])"
      >
        <DropdownItem
          v-for="aiType in aITypes"
          :key="aiType.getType()"
          :name="aiType.getName()"
          :value="aiType.getType()"
        />
      </Dropdown>
      <template #error>
        <div v-if="v$.values.ai_generative_ai_type.required.$invalid">
          {{ $t('error.requiredField') }}
        </div>
      </template>
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('selectAIModelForm.AIModel')"
      :error="fieldHasErrors('ai_generative_ai_model')"
      required
    >
      <Dropdown
        ref="aiModel"
        v-model="v$.values.ai_generative_ai_model.$model"
        class="dropdown--floating"
        :error="fieldHasErrors('ai_generative_ai_model')"
        :fixed-items="true"
        :show-search="false"
        @hide="v$.values.ai_generative_ai_model.$touch"
      >
        <DropdownItem
          v-for="aIType in aIModelsPerType"
          :key="aIType"
          :name="aIType"
          :value="aIType"
        />
      </Dropdown>
      <template #error>
        <div v-if="v$.values.ai_generative_ai_model.required.$invalid">
          {{ $t('error.requiredField') }}
        </div>
      </template>
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('selectAIModelForm.temperatureLabel')"
      :help-icon-tooltip="
        $t('selectAIModelForm.temperatureDescription', { max: maxTemperature })
      "
      :error="fieldHasErrors('ai_temperature')"
      required
    >
      <FormInput
        v-model="v$.values.ai_temperature.$model"
        :step="0.1"
        :min="0"
        :max="maxTemperature"
        type="number"
        :error="fieldHasErrors('ai_temperature')"
      ></FormInput>
      <template #error>
        <span v-if="v$.values.ai_temperature.decimal.$invalid">
          {{ $t('error.decimalField') }}
        </span>
        <span v-else-if="v$.values.ai_temperature.minValue.$invalid">
          {{ $t('error.minValueField', { min: 0 }) }}
        </span>
        <span v-else-if="v$.values.ai_temperature.maxValue.$invalid">
          {{ $t('error.maxValueField', { max: maxTemperature }) }}
        </span>
      </template>
    </FormGroup>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { mapGetters } from 'vuex'
import { required, decimal, minValue, maxValue } from '@vuelidate/validators'
import modal from '@baserow/modules/core/mixins/modal'
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'SelectAIModelForm',
  mixins: [form, modal],
  props: {
    database: {
      type: Object,
      required: true,
    },
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      allowedValues: [
        'ai_generative_ai_type',
        'ai_generative_ai_model',
        'ai_temperature',
      ],
      values: {
        ai_generative_ai_type: null,
        ai_generative_ai_model: null,
        ai_temperature: 0.1,
      },
      temperature: null,
    }
  },
  computed: {
    ...mapGetters({
      settings: 'settings/get',
    }),
    // Return the reactive object that can be updated in runtime.
    workspace() {
      return this.$store.getters['workspace/get'](this.database.workspace.id)
    },
    aITypes() {
      const types = this.workspace.generative_ai_models_enabled || {}
      return Object.keys(types).map((aiType) => {
        return this.$registry.get('generativeAIModel', aiType)
      })
    },
    aIModelsPerType() {
      return this.getAIModelsPerType(this.values.ai_generative_ai_type)
    },
    maxTemperature() {
      if (!this.values.ai_generative_ai_type) {
        return 2
      }

      return this.$registry
        .get('generativeAIModel', this.values.ai_generative_ai_type)
        .getMaxTemperature()
    },
  },
  watch: {
    'values.ai_generative_ai_type': function (newValue, oldValue) {
      this.$emit('ai-type-changed', newValue)
    },
    'values.ai_temperature'(newValue, oldValue) {
      if (newValue !== oldValue) {
        this.temperature = newValue || ''
      }
    },
    temperature(newValue, oldValue) {
      if (newValue !== oldValue) {
        if (!newValue) {
          this.values.ai_temperature = null
        } else {
          const value = parseFloat(newValue)
          if (!isNaN(value)) {
            this.values.ai_temperature = parseFloat(newValue) || null
          }
        }
      }
    },
  },
  mounted() {
    if (!this.values.ai_generative_ai_type && this.aITypes.length > 0) {
      const aiType = this.aITypes[0].getType()
      this.values.ai_generative_ai_type = aiType
      const aiModels = this.getAIModelsPerType(aiType)
      this.values.ai_generative_ai_model = aiModels[0] || null
    }
  },
  methods: {
    getAIModelsPerType(aiType) {
      return this.workspace.generative_ai_models_enabled[aiType] || []
    },
  },
  validations() {
    return {
      values: {
        ai_generative_ai_type: { required },
        ai_generative_ai_model: { required },
        ai_temperature: {
          decimal,
          minValue: minValue(0),
          maxValue: maxValue(this.maxTemperature),
        },
      },
    }
  },
}
</script>
