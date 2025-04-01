<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      required
      class="margin-bottom-2"
      small-label
      :label="$t('columnElementForm.columnAmountTitle')"
    >
      <Dropdown v-model="v$.values.column_amount.$model" :show-search="false">
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
      :error-message="getFirstErrorMessage('column_gap')"
    >
      <FormInput
        v-model="v$.values.column_gap.$model"
        :label="$t('columnElementForm.columnGapTitle')"
        :placeholder="$t('columnElementForm.columnGapPlaceholder')"
        type="number"
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
import { useVuelidate } from '@vuelidate/core'
import form from '@baserow/modules/core/mixins/form'
import { VERTICAL_ALIGNMENTS } from '@baserow/modules/builder/enums'
import {
  required,
  integer,
  minValue,
  maxValue,
  helpers,
} from '@vuelidate/validators'
import VerticalAlignmentSelector from '@baserow/modules/builder/components/VerticalAlignmentSelector'
import elementForm from '@baserow/modules/builder/mixins/elementForm'

export default {
  name: 'ColumnElementForm',
  components: {
    VerticalAlignmentSelector,
  },
  mixins: [elementForm],
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      values: {
        column_amount: 1,
        column_gap: 30,
        alignment: VERTICAL_ALIGNMENTS.TOP,
        styles: {},
      },
      allowedValues: ['column_amount', 'column_gap', 'alignment', 'styles'],
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
  },
  methods: {
    emitChange(newValues) {
      if (this.isFormValid()) {
        form.methods.emitChange.bind(this)(newValues)
      }
    },
  },
  validations() {
    return {
      values: {
        column_gap: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          integer: helpers.withMessage(this.$t('error.integerField'), integer),
          minValue: helpers.withMessage(
            this.$t('error.minValueField', { min: 0 }),
            minValue(0)
          ),
          maxValue: helpers.withMessage(
            this.$t('error.maxValueField', { max: 2000 }),
            maxValue(2000)
          ),
        },
        column_amount: {
          integer,
        },
      },
    }
  },
}
</script>
