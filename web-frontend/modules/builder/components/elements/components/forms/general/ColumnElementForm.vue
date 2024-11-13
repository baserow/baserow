<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      required
      class="margin-bottom-2"
      small-label
      :label="$t('columnElementForm.columnAmountTitle')"
    >
      <Dropdown v-model="v$.column_amount.$model" :show-search="false">
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
      :error="v$.column_gap.$error"
    >
      <FormInput
        v-model="v$.column_gap.$model"
        :label="$t('columnElementForm.columnGapTitle')"
        :placeholder="$t('columnElementForm.columnGapPlaceholder')"
        type="number"
        :error="v$.column_gap.$error"
        @blur="v$.column_gap.$touch"
      />

      <template #error>
        <span v-if="v$.column_gap.required.$invalid">
          {{ $t('error.requiredField') }}
        </span>
        <span v-else-if="v$.column_gap.integer.$invalid">
          {{ $t('error.integerField') }}
        </span>
        <span v-else-if="v$.column_gap.minValue.$invalid">
          {{ $t('error.minValueField', { min: 0 }) }}
        </span>
        <span v-else-if="v$.column_gap.maxValue.$invalid">
          {{ $t('error.maxValueField', { max: 2000 }) }}
        </span>
      </template>
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
import { reactive, computed } from 'vue'
import form from '@baserow/modules/core/mixins/form'
import { VERTICAL_ALIGNMENTS } from '@baserow/modules/builder/enums'
import { required, integer, minValue, maxValue } from '@vuelidate/validators'
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
      values: null,
      v$: null,
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
  created() {
    const values = reactive({
      column_amount: 1,
      column_gap: 30,
      alignment: VERTICAL_ALIGNMENTS.TOP,
    })

    const rules = computed(() => ({
      column_gap: {
        required,
        integer,
        minValue: minValue(0),
        maxValue: maxValue(2000),
      },
      column_amount: {
        integer,
      },
    }))
    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },

  methods: {
    async emitChange(newValues) {
      const formValid = await this.v$.$validate()
      if (formValid) {
        form.methods.emitChange.bind(this)(newValues)
      }
    },
  },
}
</script>
