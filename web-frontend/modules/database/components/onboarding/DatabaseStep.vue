<template>
  <div>
    <h1>{{ $t('databaseStep.title') }}</h1>
    <p>
      {{ $t('databaseStep.description') }}
    </p>
    <div class="margin-bottom-3">
      <SegmentControl
        :active-index.sync="selectedTypeIndex"
        :segments="types"
        :initial-active-index="0"
        @update:activeIndex="updateValue"
      ></SegmentControl>
    </div>
    <template v-if="hasName">
      <FormGroup :error="v$.name.required.$invalid">
        <FormInput
          v-model="name"
          :placeholder="$t('databaseStep.databaseNameLabel')"
          :label="$t('databaseStep.databaseNameLabel')"
          size="large"
          :error="v$.name.required.$invalid"
          @input="updateValue"
          @blur="v$.name.$touch"
        />
        <template #error>{{ v$.name.required.$errors[0].$message }}</template>
      </FormGroup>
    </template>
    <AirtableImportForm
      v-if="selectedType === 'airtable'"
      ref="airtable"
      @input=";[(airtableUrl = $event), updateValue()]"
    ></AirtableImportForm>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { requiredIf, helpers } from '@vuelidate/validators'
import SegmentControl from '@baserow/modules/core/components/SegmentControl'
import AirtableImportForm from '@baserow/modules/database/components/airtable/AirtableImportForm.vue'

export default {
  name: 'DatabaseStep',
  components: { AirtableImportForm, SegmentControl },
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
      ],
      selectedTypeIndex: 0,
      name: '',
      airtableUrl: '',
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
      return !this.v$.$invalid
    },
    updateValue() {
      this.$emit('update-data', {
        name: this.name,
        type: this.selectedType,
        airtableUrl: this.airtableUrl,
      })
    },
  },
  validations() {
    return {
      name: {
        required: helpers.withMessage(
          this.$t('error.requiredField'),
          requiredIf(() => {
            return this.hasName
          })
        ),
      },
      airtableUrl: {
        required: helpers.withMessage(
          this.$t('error.requiredField'),
          requiredIf(() => {
            return this.selectedType === 'airtable'
          })
        ),
      },
    }
  },
}
</script>
