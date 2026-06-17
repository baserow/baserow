<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      required
      class="margin-bottom-2"
      small-label
      :label="$t('columnElementForm.columnAmountTitle')"
    >
      <ColumnLayoutSelector
        v-if="!usesCustomOnlyLayout"
        v-model="values.layout_type"
        :column-amount="values.column_amount"
        @update-amount="updateColumnAmount"
        @update:model-value="onLayoutTypeChange"
      />
      <Dropdown
        v-else
        v-model="values.column_amount"
        :show-search="false"
        @input="updateColumnAmount"
      >
        <DropdownItem
          v-for="columnCount in maximumColumnAmount"
          :key="columnCount"
          :name="
            $t('columnElementForm.columnAmountName', {
              columnAmount: columnCount,
              count: columnCount,
            })
          "
          :value="columnCount"
        />
      </Dropdown>
    </FormGroup>

    <FormGroup
      :label="$t('columnElementForm.columnStackingTitle')"
      small-label
      required
      class="margin-bottom-2"
    >
      <DeviceSelector
        :device-type-selected="deviceTypeSelected"
        direction="row"
        @selected="actionSetDeviceTypeSelected"
      >
        <template #deviceTypeControl="{ deviceType }">
          <RadioButton
            v-for="stackingOption in columnStackingOptions"
            :key="stackingOption.value"
            v-model="values.column_stacking[deviceType.getType()]"
            :icon="stackingOption.icon"
            :value="stackingOption.value"
          >
            {{ stackingOption.label }}
          </RadioButton>
        </template>
      </DeviceSelector>
    </FormGroup>

    <FormGroup
      v-if="usesCustomWeights"
      class="margin-bottom-2"
      small-label
      required
      :label="$t('columnElementForm.customWeightsTitle')"
      :helper-text="$t('columnElementForm.customWeightsHelper')"
      :error-message="
        v$.custom_weights.$error ? v$.custom_weights.$errors[0].$message : ''
      "
    >
      <div class="column-element-form__custom-weights">
        <FormInput
          v-for="(weight, index) in custom_weights"
          :key="index"
          :model-value="custom_weights[index]"
          type="number"
          :min="0"
          class="column-element-form__custom-weight-input"
          @keydown="onCustomWeightKeydown"
          @update:model-value="onCustomWeightChange(index, $event)"
        />
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
      class="margin-bottom-2"
    >
      <VerticalAlignmentSelector v-model="values.alignment" />
    </FormGroup>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import form from '@baserow/modules/core/mixins/form'
import {
  COLUMN_STACKING,
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
import DeviceSelector from '@baserow/modules/builder/components/page/header/DeviceSelector.vue'
import { mapActions, mapGetters } from 'vuex'
import ColumnLayoutSelector from './ColumnLayoutSelector'

export default {
  name: 'ColumnElementForm',
  components: {
    VerticalAlignmentSelector,
    ColumnLayoutSelector,
    DeviceSelector,
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
        layout_type: 'auto',
        column_weights: [],
        column_stacking: {
          smartphone: COLUMN_STACKING.STACKED,
          tablet: COLUMN_STACKING.HORIZONTAL,
          desktop: COLUMN_STACKING.HORIZONTAL,
        },
        styles: {},
      },
      custom_weights: [],
      maximumColumnAmount: 6,
      maximumPresetColumnAmount: 3,
      columnStackingOptions: [
        {
          icon: 'iconoir-view-columns-3',
          label: this.$t('columnElementForm.columnStackingHorizontal'),
          value: COLUMN_STACKING.HORIZONTAL,
        },
        {
          icon: 'iconoir-table-rows',
          label: this.$t('columnElementForm.columnStackingStacked'),
          value: COLUMN_STACKING.STACKED,
        },
      ],
      allowedValues: [
        'column_amount',
        'column_gap',
        'alignment',
        'layout_type',
        'column_weights',
        'column_stacking',
        'styles',
      ],
    }
  },
  computed: {
    ...mapGetters({
      deviceTypeSelected: 'page/getDeviceTypeSelected',
    }),
    usesCustomOnlyLayout() {
      return this.isCustomOnlyColumnAmount(this.values.column_amount)
    },
    usesCustomWeights() {
      return this.values.layout_type === 'custom' || this.usesCustomOnlyLayout
    },
  },
  watch: {
    'values.column_amount'(newAmount) {
      if (this.custom_weights.length !== newAmount) {
        this.initCustomWeights(newAmount)
      }
      this.ensureCustomLayoutForColumnAmount()
    },
  },
  created() {
    if (this.values.column_weights?.length === this.values.column_amount) {
      this.initCustomWeights(
        this.values.column_amount,
        this.values.column_weights
      )
    } else {
      this.initCustomWeights(this.values.column_amount)
    }
    this.values.column_stacking = {
      smartphone: COLUMN_STACKING.STACKED,
      tablet: COLUMN_STACKING.HORIZONTAL,
      desktop: COLUMN_STACKING.HORIZONTAL,
      ...(this.values.column_stacking || {}),
    }
    this.ensureCustomLayoutForColumnAmount()
  },
  methods: {
    ...mapActions({
      actionSetDeviceTypeSelected: 'page/setDeviceTypeSelected',
    }),
    initCustomWeights(amount, sourceWeights = []) {
      const newWeights = Array(amount).fill(1)
      for (let i = 0; i < Math.min(amount, sourceWeights.length); i++) {
        const parsedWeight = parseFloat(sourceWeights[i])
        newWeights[i] = isNaN(parsedWeight) ? 0 : parsedWeight
      }
      this.custom_weights = newWeights
    },
    isCustomOnlyColumnAmount(amount) {
      return amount > this.maximumPresetColumnAmount
    },
    ensureCustomLayoutForColumnAmount() {
      if (this.isCustomOnlyColumnAmount(this.values.column_amount)) {
        this.values.layout_type = 'custom'
        this.values.column_weights = [...this.custom_weights]
      }
    },
    onLayoutTypeChange(newLayoutType) {
      this.values.layout_type = this.isCustomOnlyColumnAmount(
        this.values.column_amount
      )
        ? 'custom'
        : newLayoutType

      if (this.values.layout_type === 'custom') {
        this.values.column_weights = [...this.custom_weights]
      }
    },
    onCustomWeightChange(index, value) {
      const parsedValue = parseFloat(value)
      const newValue = isNaN(parsedValue) ? 0 : parsedValue

      const newWeights = [...this.custom_weights]
      newWeights[index] = newValue
      this.custom_weights = newWeights

      this.values.column_weights = [...this.custom_weights]
      this.v$.$touch()
    },
    onCustomWeightKeydown(event) {
      if (
        event.ctrlKey ||
        event.metaKey ||
        [
          'Backspace',
          'Delete',
          'Tab',
          'Escape',
          'Enter',
          'ArrowLeft',
          'ArrowRight',
          'ArrowUp',
          'ArrowDown',
          'Home',
          'End',
        ].includes(event.key)
      ) {
        return
      }

      if (/^\d$/.test(event.key)) {
        return
      }

      const currentValue = event.currentTarget?.value || ''
      if (event.key === '.' && !currentValue.includes('.')) {
        return
      }

      event.preventDefault()
    },
    updateColumnAmount(amount) {
      this.values.column_amount = amount

      if (
        this.values.layout_type === 'custom' ||
        this.isCustomOnlyColumnAmount(amount)
      ) {
        this.initCustomWeights(amount, this.values.column_weights)
        this.values.layout_type = this.isCustomOnlyColumnAmount(amount)
          ? 'custom'
          : this.values.layout_type
        this.values.column_weights = [...this.custom_weights]
      } else {
        const currentWeights = this.values.column_weights || []
        const newWeights = Array(amount).fill(1)
        for (let i = 0; i < Math.min(amount, currentWeights.length); i++) {
          newWeights[i] = currentWeights[i]
        }
        this.values.column_weights = newWeights
      }
    },
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
      custom_weights: {
        weightsAreNonNegative: helpers.withMessage(
          this.$t('columnElementForm.errorCustomWeightsMinimum'),
          (val) =>
            this.values.layout_type !== 'custom' ||
            val.every((weight) => !isNaN(weight) && weight >= 0)
        ),
      },
    }
  },
}
</script>
