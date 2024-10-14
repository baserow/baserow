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
      <FormGroup :error="$v.name.$dirty && !$v.name.required">
        <FormInput
          v-model="name"
          :placeholder="$t('databaseStep.databaseNameLabel')"
          :label="$t('databaseStep.databaseNameLabel')"
          size="large"
          :error="$v.name.$dirty && !$v.name.required"
          @input="updateValue"
          @blur="$v.name.$touch()"
        />
        <template #error>{{ $t('error.requiredField') }}</template>
      </FormGroup>
    </template>
    <ImportFromAirtable
      v-if="selectedType === 'airtable'"
      ref="airtable"
      @input=";[(airtableUrl = $event), updateValue()]"
    ></ImportFromAirtable>
  </div>
</template>

<script>
import { requiredIf } from 'vuelidate/lib/validators'
import SegmentControl from '@baserow/modules/core/components/SegmentControl'
import ImportFromAirtable from '@baserow/modules/database/components/airtable/ImportFromAirtable'

export default {
  name: 'DatabaseStep',
  components: { ImportFromAirtable, SegmentControl },
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
      return !this.$v.$invalid
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
        required: requiredIf(() => {
          return this.hasName
        }),
      },
      airtableUrl: {
        required: requiredIf(() => {
          return this.selectedType === 'airtable'
        }),
      },
    }
  },
}
</script>
