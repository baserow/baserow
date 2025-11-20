<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      required
      class="margin-bottom-2"
      small-label
      :label="$t('columnElementForm.columnAmountTitle')"
    >
      <Dropdown v-model="computedColumnAmount" :show-search="false">
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
      class="margin-bottom-2"
      required
    >
      <VerticalAlignmentSelector v-model="values.alignment" />
    </FormGroup>

    <FormGroup
      required
      class="margin-bottom-2"
      small-label
      :label="$t('columnElementForm.columnLayout')"
    >
      <Dropdown v-model="v$.values.column_layout.$model" :show-search="false">
        <DropdownItem
          v-for="columnLayout in columnLayouts"
          :key="columnLayout.value"
          :name="columnLayout.name"
          :value="columnLayout.value"
        >
          {{ columnLayout.name }}
        </DropdownItem>
      </Dropdown>
    </FormGroup>

    <template v-if="v$.values.column_layout.$model === 'manual'">
      <FormGroup
        v-for="(weight, index) in v$.values.column_weights.$model"
        :key="`${computedColumnAmount}-${index}`"
        small-label
        horizontal
        required
        class="margin-bottom-1"
        :label="$t('columnElementForm.columnWeight')"
      >
        <FormInput
          :value="weight"
          :label="$t('columnElementForm.columnWeight')"
          :placeholder="$t('columnElementForm.columnWeightPlaceholder')"
          type="number"
          @input="setColumnWeight(index, $event)"
        />
      </FormGroup>
    </template>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import form from '@baserow/modules/core/mixins/form'
import {
  COLUMN_LAYOUTS,
  VERTICAL_ALIGNMENTS,
} from '@baserow/modules/builder/enums'
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
        column_layout: 'auto',
        column_weights: [],
        column_gap: 30,
        alignment: VERTICAL_ALIGNMENTS.TOP,
        styles: {},
      },
      allowedValues: [
        'column_amount',
        'column_gap',
        'alignment',
        'column_layout',
        'column_weights',
        'styles',
      ],
    }
  },
  computed: {
    columnAmounts() {
      const maximumColumnAmount = 6
      return [...Array(maximumColumnAmount).keys()].map((columnAmount) => ({
        name: this.$t('columnElementForm.columnAmountName', {
          columnAmount: columnAmount + 1,
          count: columnAmount + 1,
        }),
        value: columnAmount + 1,
      }))
    },
    columnLayouts() {
      return [
        {
          name: this.$t('columnElementForm.layoutAuto'),
          value: COLUMN_LAYOUTS.AUTO,
        },
        {
          name: this.$t('columnElementForm.layoutFlexi'),
          value: COLUMN_LAYOUTS.FLEXI,
        },
        {
          name: this.$t('columnElementForm.layoutManual'),
          value: COLUMN_LAYOUTS.MANUAL,
        },
      ]
    },
    computedColumnAmount: {
      get() {
        return this.v$.values.column_amount.$model
      },
      set(newValue) {
        this.v$.values.column_weights.$model = [...Array(newValue).keys()].map(
          (index) => {
            return this.v$.values.column_weights.$model[index] ?? 0
          }
        )
        this.v$.values.column_amount.$model = newValue
      },
    },
  },
  methods: {
    emitChange(newValues) {
      if (this.isFormValid()) {
        form.methods.emitChange.bind(this)(newValues)
      }
    },
    setColumnWeight(index, newValue) {
      this.v$.values.column_weights.$model =
        this.v$.values.column_weights.$model.map((value, idx) => {
          if (index === idx) {
            return parseInt(newValue)
          }
          return value
        })
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
        column_layout: {},
        column_weights: {},
      },
    }
  },
}
</script>
