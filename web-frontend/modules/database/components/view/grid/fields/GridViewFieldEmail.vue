<template>
  <div
    class="grid-view__cell active"
    :class="{
      editing: editing,
      invalid: editing && !valid,
    }"
    @contextmenu="stopContextIfEditing($event)"
  >
    <div v-show="!editing" class="grid-field-text">
      <a
        :href="'mailto:' + value"
        target="_blank"
        rel="nofollow noopener noreferrer"
        >{{ value }}</a
      >
    </div>
    <template v-if="editing">
      <input
        ref="input"
        v-model="copy"
        type="text"
        class="grid-field-text__input"
      />
      <div v-show="!valid" class="grid-view__cell-error align-right">
        {{ error }}
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
