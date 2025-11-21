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
      :label="$t('columnElementForm.layoutTypeTitle')"
    >
      <Dropdown v-model="values.layout_type" :show-search="false">
        <DropdownItem
          v-for="layoutType in availableLayoutTypes"
          :key="layoutType.value"
          :name="layoutType.name"
          :value="layoutType.value"
        >
          {{ layoutType.name }}
        </DropdownItem>
      </Dropdown>
    </FormGroup>

    <FormGroup
      v-if="values.layout_type === 'custom'"
      class="margin-bottom-2"
      small-label
      :label="$t('columnElementForm.customWidthsTitle')"
    >
      <div
        v-for="(width, index) in values.column_widths"
        :key="index"
        class="margin-bottom-1"
      >
        <label class="control__label">
          {{ $t('columnElementForm.columnLabel', { index: index + 1 }) }}
        </label>
        <Dropdown v-model="values.column_widths[index]" :show-search="false">
          <DropdownItem name="Auto" value="auto">Auto</DropdownItem>
          <DropdownItem name="Dynamic (fills space)" value="dynamic">
            Dynamic
          </DropdownItem>
          <DropdownItem
            v-for="px in fixedWidthOptions"
            :key="px"
            :name="`${px}px`"
            :value="px"
          >
            {{ px }}px
          </DropdownItem>
        </Dropdown>
      </div>
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
        column_gap: 20,
        alignment: VERTICAL_ALIGNMENTS.TOP,
        layout_type: 'auto',
        column_widths: [],
        styles: {},
      },
      allowedValues: [
        'column_amount',
        'column_gap',
        'alignment',
        'layout_type',
        'column_widths',
        'styles',
      ],
      fixedWidthOptions: [100, 150, 200, 250, 300, 350, 400, 500],
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
    availableLayoutTypes() {
      const amount = this.values.column_amount
      const types = [
        { name: 'Auto (equal widths)', value: 'auto' },
        { name: 'Custom', value: 'custom' },
      ]

      if (amount === 2) {
        types.push(
          { name: '1:2 (narrow:wide)', value: '1:2' },
          { name: '2:1 (wide:narrow)', value: '2:1' }
        )
      }

      if (amount === 3) {
        types.push(
          { name: '1:1:2 (narrow:narrow:wide)', value: '1:1:2' },
          { name: '2:1:1 (wide:narrow:narrow)', value: '2:1:1' }
        )
      }

      return types
    },
  },
  watch: {
    'values.column_amount'(newAmount, oldAmount) {
      const availableValues = this.availableLayoutTypes.map((t) => t.value)
      if (!availableValues.includes(this.values.layout_type)) {
        this.values.layout_type = 'auto'
      }

      if (this.values.layout_type === 'custom') {
        this.initializeColumnWidths(newAmount)
      }
    },
    'values.layout_type'(newType) {
      if (newType === 'custom') {
        this.initializeColumnWidths(this.values.column_amount)
      }
    },
  },
  methods: {
    emitChange(newValues) {
      if (this.isFormValid()) {
        form.methods.emitChange.bind(this)(newValues)
      }
    },
    initializeColumnWidths(amount) {
      if (this.values.column_widths.length === amount) return

      this.values.column_widths = Array(amount).fill('auto')
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
