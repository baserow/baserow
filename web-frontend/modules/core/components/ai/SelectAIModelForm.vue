<template>
  <div class="context__form-container">
    <FormGroup
      small-label
      :label="$t('selectAIModelForm.AIType')"
      :error="$v.values.ai_generative_ai_type.$error"
      required
    >
      <Dropdown
        v-model="values.ai_generative_ai_type"
        class="dropdown--floating"
        :error="$v.values.ai_generative_ai_type.$errors"
        :fixed-items="true"
        :show-search="false"
        @hide="$v.values.ai_generative_ai_type.$touch()"
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
        <div
          v-if="
            $v.values.ai_generative_ai_type.$dirty &&
            !$v.values.ai_generative_ai_type.required
          "
        >
          {{ $t('error.requiredField') }}
        </div>
      </template>
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('selectAIModelForm.AIModel')"
      :error="$v.values.ai_generative_ai_model.$error"
      required
    >
      <Dropdown
        ref="aiModel"
        v-model="values.ai_generative_ai_model"
        class="dropdown--floating"
        :error="$v.values.ai_generative_ai_model.$error"
        :fixed-items="true"
        :show-search="false"
        @hide="$v.values.ai_generative_ai_model.$touch()"
      >
        <DropdownItem
          v-for="aIType in aIModelsPerType"
          :key="aIType"
          :name="aIType"
          :value="aIType"
        />
      </Dropdown>
      <template #error>
        <div
          v-if="
            $v.values.ai_generative_ai_model.$dirty &&
            !$v.values.ai_generative_ai_model.required
          "
        >
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
      :error="$v.values.ai_temperature.$error"
      required
    >
      <FormInput
        v-model="temperature"
        :step="0.1"
        :min="0"
        :max="maxTemperature"
        type="number"
        :error="$v.values.ai_temperature.$error"
        @blur="$v.values.ai_temperature.$touch()"
      ></FormInput>
      <template #error>
        <div v-if="$v.values.ai_temperature.$error">
          {{ temperatureErrorMessage }}
        </div>
      </template>
    </FormGroup>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import { required, decimal, minValue, maxValue } from 'vuelidate/lib/validators'
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
        ai_temperature: null,
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
      return (
        this.workspace.generative_ai_models_enabled[
          this.values.ai_generative_ai_type
        ] || []
      )
    },
    maxTemperature() {
      if (!this.values.ai_generative_ai_type) {
        return 2
      }

      return this.$registry
        .get('generativeAIModel', this.values.ai_generative_ai_type)
        .getMaxTemperature()
    },
    temperatureErrorMessage() {
      return this.$v.values.ai_temperature.$dirty &&
        !this.$v.values.ai_temperature.decimal
        ? this.$t('error.decimalField')
        : !this.$v.values.ai_temperature.minValue
        ? this.$t('error.minValueField', { min: 0 })
        : !this.$v.values.ai_temperature.maxValue
        ? this.$t('error.maxValueField', { max: this.maxTemperature })
        : ''
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
