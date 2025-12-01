<template>
  <div
    class="grid-view__cell active"
    :class="{
      editing: editing,
      invalid: editing && !isValid(),
    }"
    @contextmenu="stopContextIfEditing($event)"
  >
    <div v-show="!editing" class="grid-field-duration">
      {{ formattedValue }}
    </div>
    <template v-if="editing">
      <input
        ref="input"
        v-model="formattedValue"
        type="text"
        class="grid-field-duration__input"
        :placeholder="field.duration_format"
        @keypress="onKeyPress(field, $event)"
        @input="onInput(field, $event)"
      />
      <div v-show="!isValid()" class="grid-view__cell-error align-right">
        {{ getError() }}
      </div>
    </template>
  </div>
</template>

<script>
import gridField from '@baserow/modules/database/mixins/gridField'
import gridFieldInput from '@baserow/modules/database/mixins/gridFieldInput'
import durationField from '@baserow/modules/database/mixins/durationField'

export default {
  mixins: [gridField, gridFieldInput, durationField],
  methods: {
    cancel() {
      this.$super(gridFieldInput).cancel()
      this.updateFormattedValue(this.field, this.copy)
    },
    beforeSave(value) {
      this.updateFormattedValue(this.field, value)
      return this.$super(gridFieldInput).beforeSave(value)
    },
    afterEdit(event, value) {
      if (value !== null) {
        this.updateCopy(this.field, value)
        this.updateFormattedValue(this.field, this.copy)
      }
      this.$nextTick(() => {
        this.$refs.input.focus()
        this.$refs.input.selectionStart = this.$refs.input.selectionEnd = 100000
      })
    },
  },
}
</script>
