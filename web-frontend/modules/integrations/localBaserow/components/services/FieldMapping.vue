<template>
  <InjectedFormulaInput
    v-model="fieldValue"
    :disabled="!fieldMapping.enabled"
    v-bind="$attrs"
  />
</template>

<script>
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'

export default {
  name: 'FieldMapping',
  components: { InjectedFormulaInput },
  props: {
    fieldMapping: {
      type: Object,
      required: true,
    },
  },
  computed: {
    fieldValue: {
      get() {
        return this.fieldMapping.value
      },
      set(value) {
        this.$emit('change', { value })
      },
    },
  },
}
</script>
