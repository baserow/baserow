<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      required
      class="margin-bottom-2"
      small-label
      :label="$t('columnElementForm.columnAmountTitle')"
    >
      <Dropdown v-model="values.column_amount" :show-search="false">
        <DropdownItem
          v-for="columnAmount in columnAmounts"
          :key="columnAmount.value"
          :name="columnAmount.name"
          :value="columnAmount.value"
        >
          {{ columnAmount.name }}
        </DropdownItem>
      </Dropdown>
    </FormGroup>

    <FormGroup
      class="margin-bottom-2"
      small-label
      required
      :label="$t('columnElementForm.columnGapTitle')"
      :error-message="errorMessage"
    >
      <FormInput
        v-model="values.column_gap"
        :label="$t('columnElementForm.columnGapTitle')"
        :placeholder="$t('columnElementForm.columnGapPlaceholder')"
        type="number"
        @blur="$v.values.column_gap.$touch()"
      />
    </FormGroup>

    <FormGroup
      :label="$t('columnElementForm.verticalAlignment')"
      small-label
      required
    >
      <VerticalAlignmentSelector v-model="values.alignment" />
    </FormGroup>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import { VERTICAL_ALIGNMENTS } from '@baserow/modules/builder/enums'
import { required, integer, minValue, maxValue } from 'vuelidate/lib/validators'
import VerticalAlignmentSelector from '@baserow/modules/builder/components/VerticalAlignmentSelector'
import elementForm from '@baserow/modules/builder/mixins/elementForm'

export default {
  name: 'ColumnElementForm',
  components: {
    VerticalAlignmentSelector,
  },
  mixins: [elementForm],
  data() {
    return {
      values: {
        column_amount: 1,
        column_gap: 30,
        alignment: VERTICAL_ALIGNMENTS.TOP,
      },
    }
  },
  computed: {
    columnAmounts() {
      const maximumColumnAmount = 6
      return [...Array(maximumColumnAmount).keys()].map((columnAmount) => ({
        name: this.$tc('columnElementForm.columnAmountName', columnAmount + 1, {
          columnAmount: columnAmount + 1,
        }),
        value: columnAmount + 1,
      }))
    },
    errorMessage() {
      return this.$v.values.column_gap.$dirty &&
        !this.$v.values.column_gap.required
        ? this.$t('error.requiredField')
        : !this.$v.values.column_gap.integer
        ? this.$t('error.integerField')
        : !this.$v.values.column_gap.minValue
        ? this.$t('error.minValueField', { min: 0 })
        : !this.$v.values.column_gap.maxValue
        ? this.$t('error.maxValueField', { max: 2000 })
        : ''
    },
  },
  methods: {
    emitChange(newValues) {
      if (this.isFormValid()) {
        form.methods.emitChange.bind(this)(newValues)
      }
    },
  },
  validations: {
    values: {
      column_gap: {
        required,
        integer,
        minValue: minValue(0),
        maxValue: maxValue(2000),
      },
    },
  },
}
</script>
