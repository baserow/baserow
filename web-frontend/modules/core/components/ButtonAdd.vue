<template>
  <button class="button-add" :disabled="disabled" v-on="$attrs">
    <i class="button-add__icon iconoir-plus" />
  </button>
</template>

<script>
export default {
  props: {
    /**
     * If true the button will be disabled.
     */
    disabled: {
      required: false,
      type: Boolean,
      default: false,
    },
  },
}
</script>
