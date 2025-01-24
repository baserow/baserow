<template>
  <Checkbox :checked="copy" :disabled="disabled" @input="input($event)">
    {{ $t('viewFilterTypeBoolean.selected') }}
  </Checkbox>
</template>

<script>
import { trueValues } from '@baserow/modules/core/utils/constants'
import viewFilter from '@baserow/modules/database/mixins/viewFilter'

export default {
  name: 'ViewFilterTypeBoolean',
  mixins: [viewFilter],
  computed: {
    copy() {
      const value = String(this.filter.value ?? '')
        .toLowerCase()
        .trim()
      return trueValues.includes(value)
    },
  },
  methods: {
    input(value) {
      this.$emit('input', value ? '1' : '0')
    },
  },
}
</script>
