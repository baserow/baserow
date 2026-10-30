<template>
  <div>
    <template v-if="rows.length">
      <div class="row" style="--gap: 6px">
        <label class="col col-5 control__label control__label--small">
          {{ $t('coreHTTPRequestServiceForm.name') }}
        </label>
        <label class="col col-7 control__label control__label--small">
          {{ $t('coreHTTPRequestServiceForm.value') }}
        </label>
      </div>
      <div
        v-for="(row, index) in rows"
        :key="row.id"
        style="--gap: 6px"
        class="row margin-bottom-1"
      >
        <div class="col col-5">
          <FormInput
            :model-value="row.key"
            :error="!!errorAt(index)"
            :placeholder="$t('coreHTTPRequestServiceForm.namePlaceholder')"
            @update:model-value="updateRow(index, { key: $event })"
            @blur="v$.$touch()"
          />
        </div>
        <div class="col col-5">
          <InjectedFormulaInput
            :model-value="row.value"
            :placeholder="$t('coreHTTPRequestServiceForm.valuePlaceholder')"
            @update:model-value="updateRow(index, { value: $event })"
          />
        </div>
        <div class="col col-2">
          <ButtonIcon icon="iconoir-bin" @click="deleteRow(row)" />
        </div>
        <div v-show="errorAt(index)" class="error margin-left-1">
          {{ errorAt(index) }}
        </div>
      </div>
    </template>
    <ButtonText
      type="secondary"
      size="small"
      icon="iconoir-plus"
      @click="createRow"
    >
      {{ addLabel }}
    </ButtonText>
  </div>
</template>

<script setup>
/**
 * The editable list of key/value pairs of an HTTP request, like its headers or
 * query params, where each value is a formula.
 */
import { computed } from 'vue'
import { useVuelidate } from '@vuelidate/core'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import { uuid } from '@baserow/modules/core/utils/string'
import { httpKeyValueRowsRules } from '@baserow/modules/integrations/core/validators'

const { $i18n } = useNuxtApp()

const props = defineProps({
  /**
   * The prefix of the key a new row gets, followed by its position.
   */
  keyPrefix: {
    type: String,
    required: true,
  },
  addLabel: {
    type: String,
    required: true,
  },
})

const rows = defineModel({ type: Array, default: () => [] })

const rules = {
  rows: httpKeyValueRowsRules((...args) => $i18n.t(...args)),
}

const v$ = useVuelidate(rules, { rows: computed(() => rows.value) })

const errorAt = (index) => v$.value.rows.$each.$message[index]?.[0]

const updateRow = (index, changes) => {
  rows.value = rows.value.map((row, rowIndex) =>
    rowIndex === index ? { ...row, ...changes } : row
  )
}

const createRow = () => {
  rows.value = [
    ...rows.value,
    {
      key: `${props.keyPrefix}${rows.value.length + 1}`,
      value: { formula: '', mode: 'simple' },
      id: uuid(),
    },
  ]
}

const deleteRow = ({ id }) => {
  rows.value = rows.value.filter((row) => row.id !== id)
}
</script>
