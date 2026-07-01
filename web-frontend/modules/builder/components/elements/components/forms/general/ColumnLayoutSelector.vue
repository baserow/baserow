<template>
  <div class="column-layout-selector">
    <Dropdown
      v-model="selectedColumnCount"
      :show-search="false"
      @input="onColumnCountChange"
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

    <div
      v-if="currentLayoutGroup.options.length > 0"
      class="column-layout-selector__options"
    >
      <div
        v-for="option in currentLayoutGroup.options"
        :key="option.value + option.amount"
        class="column-layout-selector__option"
        :class="{
          'column-layout-selector__option--active':
            modelValue === option.value && columnAmount === option.amount,
        }"
        @click="selectLayout(option)"
      >
        <div class="column-layout-selector__icon">
          <div
            v-for="(weight, index) in option.weights"
            :key="index"
            class="column-layout-selector__icon-column"
            :class="{
              'column-layout-selector__icon-column--custom':
                option.value === 'custom',
            }"
            :style="{ flex: weight }"
          ></div>
        </div>
        <div class="column-layout-selector__label">{{ option.label }}</div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ColumnLayoutSelector',
  props: {
    modelValue: {
      type: String,
      required: true,
    },
    columnAmount: {
      type: Number,
      required: true,
    },
  },
  emits: ['update:modelValue', 'update-amount'],
  data() {
    return {
      selectedColumnCount: this.columnAmount,
      maximumColumnAmount: 6,
    }
  },
  computed: {
    layoutsByColumnCount() {
      const autoLayout = (amount) => ({
        value: 'auto',
        amount,
        label: Array(amount).fill(1).join(':'),
        weights: Array(amount).fill(1),
      })
      const customLayout = (amount) => ({
        value: 'custom',
        amount,
        label: this.$t('columnElementForm.customLayout'),
        weights: Array(amount).fill(1),
      })

      return {
        1: {
          options: [],
        },
        2: {
          options: [
            autoLayout(2),
            { value: '1:2', amount: 2, label: '1:2', weights: [1, 2] },
            { value: '2:1', amount: 2, label: '2:1', weights: [2, 1] },
            { value: '1:3', amount: 2, label: '1:3', weights: [1, 3] },
            { value: '3:1', amount: 2, label: '3:1', weights: [3, 1] },
            customLayout(2),
          ],
        },
        3: {
          options: [
            autoLayout(3),
            { value: '1:1:2', amount: 3, label: '1:1:2', weights: [1, 1, 2] },
            { value: '2:1:1', amount: 3, label: '2:1:1', weights: [2, 1, 1] },
            { value: '1:2:1', amount: 3, label: '1:2:1', weights: [1, 2, 1] },
            customLayout(3),
          ],
        },
        4: {
          options: [],
        },
        5: {
          options: [],
        },
        6: {
          options: [],
        },
      }
    },
    currentLayoutGroup() {
      return (
        this.layoutsByColumnCount[this.selectedColumnCount] || { options: [] }
      )
    },
  },
  watch: {
    columnAmount(newVal) {
      this.selectedColumnCount = newVal
    },
  },
  methods: {
    onColumnCountChange(count) {
      this.selectedColumnCount = count
      this.$emit('update-amount', count)
      this.$emit('update:modelValue', count > 3 ? 'custom' : 'auto')
    },
    selectLayout(option) {
      this.$emit('update-amount', option.amount)
      this.$emit('update:modelValue', option.value)
    },
  },
}
</script>
