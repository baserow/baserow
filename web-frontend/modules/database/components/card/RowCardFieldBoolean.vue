<template>
  <div class="card-boolean">
    <i v-if="!!value" class="iconoir-check"></i>
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
