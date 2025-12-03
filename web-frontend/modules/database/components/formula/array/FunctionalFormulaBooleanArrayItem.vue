<template>
  <div class="array-field__boolean">
    <div class="array-field__checkbox">
      <i v-if="value" class="iconoir-check"></i>
      <i v-else class="iconoir-cancel array-field__checkbox--false"></i>
    </div>
  </div>
</template>

<script>
export default {
  name: 'FunctionalFormulaBooleanArrayItem',
  props: {
    value: {
      type: Boolean,
      default: false,
    },
  },
}
</script>
