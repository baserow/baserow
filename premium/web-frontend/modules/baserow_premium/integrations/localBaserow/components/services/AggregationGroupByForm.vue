<template>
  <FormSection
    :title="$t('aggregationGroupByForm.groupByFieldLabel')"
    class="margin-bottom-2"
  >
    <Dropdown
      :value="aggregationGroupBy"
      :show-search="true"
      :error="v$.aggregationGroupBy?.$error || false"
      fixed-items
      @change="groupByChangedByUser($event)"
    >
      <DropdownItem
        v-for="groupByOption in groupByOptions"
        :key="groupByOption.id"
        :name="groupByOption.name"
        :value="groupByOption.value"
      >
        {{ groupByOption.name }}
      </DropdownItem>
    </Dropdown>
    <FormGroup
      v-if="isMultipleValueRelation"
      :label="$t('aggregationGroupByForm.modeLabel')"
      class="margin-top-2"
    >
      <Dropdown
        :value="aggregationMode"
        fixed-items
        @change="modeChangedByUser($event)"
      >
        <DropdownItem
          value="complete"
          :name="$t('aggregationGroupByForm.completeSelection')"
        />
        <DropdownItem
          value="individual"
          :name="$t('aggregationGroupByForm.eachOption')"
        />
      </Dropdown>
    </FormGroup>
    <FormGroup
      v-if="aggregationGroupBy !== 'none'"
      :label="$t('aggregationGroupByForm.bucketLimit')"
      class="margin-top-2"
    >
      <FormInput
        :model-value="bucketLimitInput ?? ''"
        type="number"
        :min="1"
        :max="maxBucketLimit"
        :placeholder="String(maxBucketLimit)"
        :error="v$.bucketLimitInput.$error"
        @update:model-value="bucketLimitChangedByUser($event)"
        @blur="bucketLimitBlurred"
      />
      <template #helper>{{
        $t('aggregationGroupByForm.bucketLimitHelp', { max: maxBucketLimit })
      }}</template>
    </FormGroup>
  </FormSection>
</template>

<script>
import debounce from 'lodash/debounce'
import { useVuelidate } from '@vuelidate/core'

// The dashboard saves every emitted value straight away, so wait until the user
// stops typing before emitting (typing `10` must not save `1` first). Same delay
// as the builder's debounced element and data source updates.
const BUCKET_LIMIT_EMIT_DELAY_MS = 500

export default {
  name: 'AggregationGroupByForm',
  emits: ['value-changed', 'mode-changed', 'bucket-limit-changed'],
  props: {
    bucketLimit: { type: Number, default: null },
    tableFields: {
      type: Array,
      required: true,
    },
    aggregationGroupBys: {
      type: Array,
      required: true,
    },
  },
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      aggregationGroupBy: 'none',
      aggregationMode: 'complete',
      // What the user typed. It only reaches the parent through
      // `bucket-limit-changed` once it is valid and the user paused or left the
      // input, so `bucketLimit` can lag behind while typing.
      bucketLimitInput: null,
      // True from the first keystroke until the typed value has been emitted or
      // the input lost focus.
      bucketLimitDirty: false,
    }
  },
  computed: {
    maxBucketLimit() {
      return Number(
        this.$config.public.baserowPremiumGroupedAggregateServiceMaxAggBuckets
      )
    },
    isMultipleValueRelation() {
      return ['link_row', 'multiple_collaborators', 'multiple_select'].includes(
        this.tableFields.find((field) => field.id === this.aggregationGroupBy)
          ?.type
      )
    },
    compatibleFields() {
      return this.tableFields.filter((field) =>
        this.$registry.get('field', field.type).getCanGroupByInView(field)
      )
    },
    groupByOptions() {
      const tableFieldOptions = this.compatibleFields.map((field) => {
        return {
          name: field.name,
          value: field.id,
        }
      })
      return tableFieldOptions.concat([
        {
          name: this.$t('aggregationGroupByForm.groupByRowId'),
          value: null,
        },
        { name: this.$t('aggregationGroupByForm.groupByNone'), value: 'none' },
      ])
    },
  },
  watch: {
    aggregationGroupBys: {
      handler(aggregationGroupBys) {
        this.aggregationMode = aggregationGroupBys[0]?.mode ?? 'complete'
        if (aggregationGroupBys.length === 0) {
          this.aggregationGroupBy = 'none'
        } else {
          this.aggregationGroupBy = aggregationGroupBys[0].field_id
        }
      },
      immediate: true,
    },
    bucketLimit: {
      handler(bucketLimit) {
        // A save response arriving while the user is still typing must not
        // overwrite what they typed.
        if (!this.bucketLimitDirty) {
          this.bucketLimitInput = bucketLimit
        }
      },
      immediate: true,
    },
  },
  created() {
    this.debouncedEmitBucketLimit = debounce(
      this.emitBucketLimit,
      BUCKET_LIMIT_EMIT_DELAY_MS
    )
  },
  mounted() {
    this.v$.$touch()
  },
  beforeUnmount() {
    this.debouncedEmitBucketLimit.cancel()
  },
  validations() {
    return {
      bucketLimitInput: {
        validLimit: (value) =>
          value === null ||
          (Number.isInteger(value) &&
            value >= 1 &&
            value <= this.maxBucketLimit),
      },
      aggregationGroupBy: {
        isValidGroupBy: (value) => {
          const validGroupByValues = this.groupByOptions.map(
            (item) => item.value
          )
          return validGroupByValues.includes(value)
        },
      },
    }
  },
  methods: {
    modeChangedByUser(value) {
      this.aggregationMode = value
      this.$emit('mode-changed', value)
    },
    groupByChangedByUser(value) {
      this.aggregationGroupBy = value
      this.$emit('value-changed', value)
    },
    bucketLimitChangedByUser(rawValue) {
      // A number input reports `''` for an empty or non-numeric value; `NaN`
      // only comes from a non-numeric string and fails `validLimit`.
      this.bucketLimitInput = rawValue === '' ? null : Number(rawValue)
      this.bucketLimitDirty = true
      this.v$.bucketLimitInput.$touch()
      if (this.v$.bucketLimitInput.$invalid) {
        // Keep showing the error instead of saving a value the backend rejects.
        this.debouncedEmitBucketLimit.cancel()
        return
      }
      this.debouncedEmitBucketLimit()
    },
    bucketLimitBlurred() {
      this.debouncedEmitBucketLimit.flush()
      this.bucketLimitDirty = false
    },
    emitBucketLimit() {
      this.bucketLimitDirty = false
      if (this.bucketLimitInput !== this.bucketLimit) {
        this.$emit('bucket-limit-changed', this.bucketLimitInput)
      }
    },
  },
}
</script>
