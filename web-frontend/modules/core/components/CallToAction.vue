<template>
  <div class="call-to-action" @click="$emit('click')">
    <slot></slot>
    <Avatar
      v-if="icon"
      :icon="icon"
      :color="iconColor"
      :rounded="iconRounded"
      :size="iconSize"
    />
  </div>
</template>

<script>
export default {
  name: 'CallToAction',
  props: {
    icon: {
      type: String,
      required: false,
      default: '',
    },
    iconColor: {
      type: String,
      required: false,
      default: 'blue',
    },
    iconRounded: {
      type: Boolean,
      required: false,
      default: false,
    },
    iconSize: {
      type: String,
      required: false,
      default: 'medium',
    },
  },
  emits: ['click'],
}
</script>
