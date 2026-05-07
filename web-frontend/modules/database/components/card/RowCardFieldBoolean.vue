<template>
  <div
    :class="[
      'card-boolean',
      value ? 'card-boolean--true' : 'card-boolean--false',
    ]"
  >
    <i v-if="!!value" class="iconoir-check"></i>
    <i v-else class="iconoir-cancel"></i>
  </div>
</template>

<script>
export default {
  name: 'RowCardFieldBoolean',
  height: 13,
  props: {
    value: {
      type: Boolean,
      default: false,
    },
  },
}
</script>
