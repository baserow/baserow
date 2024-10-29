<template>
  <form @submit.prevent="submit">
    <FormGroup
      :style="{ width: '100%' }"
      :error="fieldHasErrors('name')"
      small-label
      required
    >
      <slot name="select-applications"> </slot>

      <template #after-input>
        <slot></slot>
      </template>
    </FormGroup>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'ImportWorkspaceForm',
  mixins: [form],
  data() {
    return {
      values: {},
    }
  },
  validations() {
    return {
      values: {},
    }
  },
}
</script>
