<template>
  <div
    ref="cell"
    class="grid-view__cell active"
    :class="{ editing: editing, invalid: editing && !isValid() }"
    @contextmenu="stopContextIfEditing($event)"
  >
    <div v-if="!editing" class="grid-field-text">{{ value }}</div>
    <template v-else>
      <input
        ref="input"
        v-model="copy"
        type="text"
        class="grid-field-text__input"
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

export default {
  mixins: [gridField, gridFieldInput],
  methods: {
    afterEdit() {
      this.$nextTick(() => {
        this.$refs.input.focus()
        this.$refs.input.selectionStart = this.$refs.input.selectionEnd = 100000
      })
    },
  },
}
</script>
