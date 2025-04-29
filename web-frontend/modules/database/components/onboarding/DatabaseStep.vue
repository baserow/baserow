<template>
  <div>
    <h1>{{ $t('databaseStep.title') }}</h1>
    <p>
      {{ $t('databaseStep.description') }}
    </p>
    <div class="margin-bottom-2">
      <SegmentControl
        :active-index.sync="selectedTypeIndex"
        :segments="types"
        :initial-active-index="0"
        @update:activeIndex="updateValue"
      ></SegmentControl>
    </div>
    <template v-if="hasName">
      <FormGroup :error="v$.name.$error">
        <FormInput
          v-model="name"
          :placeholder="$t('databaseStep.databaseNameLabel')"
          :label="$t('databaseStep.databaseNameLabel')"
          size="large"
          :error="v$.name.$error"
          @input=";[v$.name.$touch(), updateValue()]"
          @blur="v$.name.$touch"
        />
        <template #error>{{ v$.name.$errors[0].$message }}</template>
      </FormGroup>
    </template>
    <AirtableImportForm
      v-if="selectedType === 'airtable'"
      ref="airtable"
      @input="updateValue($event)"
    ></AirtableImportForm>
    <TemplateImportForm
      v-if="selectedType === 'template'"
      @selected-template="selectedTemplate"
    ></TemplateImportForm>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required, helpers } from '@vuelidate/validators'
import AirtableImportForm from '@baserow/modules/database/components/airtable/AirtableImportForm'
import TemplateImportForm from '@baserow/modules/database/components/onboarding/TemplateImportForm'
import { DatabaseOnboardingType } from '@baserow/modules/database/onboardingTypes'

export default {
  name: 'DatabaseStep',
  components: { AirtableImportForm, TemplateImportForm },
  props: {
    data: {
      required: true,
      type: Object,
    },
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      types: [
        {
          type: 'scratch',
          label: this.$t('databaseStep.scratch'),
        },
        {
          type: 'import',
          label: this.$t('databaseStep.import'),
        },
        {
          type: 'airtable',
          label: this.$t('databaseStep.airtable'),
        },
        {
          type: 'template',
          label: this.$t('databaseStep.template'),
        },
      ],
      selectedTypeIndex: 0,
      name: '',
    }
  },

  computed: {
    selectedType() {
      return this.types[this.selectedTypeIndex].type
    },
    hasName() {
      return ['scratch', 'import'].includes(this.selectedType)
    },
  },
  mounted() {
    this.updateValue()
  },
  methods: {
    isValid() {
      if (this.selectedType === 'airtable') {
        const airtable = this.$refs.airtable
        return !!airtable && !airtable.v$.$invalid && airtable.v$.$dirty
      } else if (this.selectedType === 'template') {
        const template = this.data[DatabaseOnboardingType.getType()].template
        return !!template
      } else {
        return !this.v$.$invalid && this.v$.$dirty
      }
    },
    updateValue(airtable = {}) {
      this.$emit('update-data', {
        name: this.name,
        type: this.selectedType,
        ...airtable,
      })
    },
    selectedTemplate(template) {
      this.$emit('update-data', {
        type: this.selectedType,
        template,
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
