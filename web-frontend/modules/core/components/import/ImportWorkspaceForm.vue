<template>
  <form @submit.prevent="submit">
    <FormGroup :style="{ width: '100%' }" small-label required>
      <slot name="select-applications"> </slot>

      <template #after-input>
        <slot></slot>
      </template>
    </FormGroup>
  </form>
</template>

<script>
export default {
  name: 'ImportWorkspaceForm',
}
</script>
