<template>
  <div class="control__elements">
    <div
      class="field-boolean__checkbox"
      :class="{ active: value, 'field-boolean__checkbox--disabled': readOnly }"
      @click="toggle(value)"
    >
      <i class="iconoir-check check field-boolean__checkbox-icon"></i>
    </div>
    <div v-show="touched && !valid" class="error">
      {{ error }}
    </div>
  </div>
</template>

<script>
import rowEditField from '@baserow/modules/database/mixins/rowEditField'

export default {
  mixins: [rowEditField],
  emits: ['update'],
  methods: {
    toggle(value) {
      if (this.readOnly) {
        return
      }

      const oldValue = !!value
      const newValue = !value
      this.$emit('update', newValue, oldValue)
      this.touch()
    },
  },
}
</script>
