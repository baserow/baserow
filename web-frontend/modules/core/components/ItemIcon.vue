<template>
  <div class="item-icon" :class="{ [`item-icon--${color}`]: color }">
    <div v-if="loading" class="loading"></div>
    <i v-else :class="icon"></i>
  </div>
</template>

<script>
/**
 * The framed icon that identifies an application or one of its items in the
 * listing pages. The frame takes the color of an application type, or the icon
 * carries its own color classes.
 */
export default {
  name: 'ItemIcon',
  props: {
    icon: {
      type: String,
      required: true,
    },
    color: {
      type: String,
      required: false,
      default: null,
      validator(value) {
        return ['blue', 'green', 'magenta', 'yellow'].includes(value)
      },
    },
    loading: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
}
</script>
