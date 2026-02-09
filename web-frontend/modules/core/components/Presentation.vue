<template>
  <div class="presentation" @click="$emit('click', $event)">
    <div v-if="image || icon || initials" class="presentation__avatar">
      <Avatar
        :size="iconSize"
        :image="image"
        :icon="icon"
        :initials="initials"
        :color="avatarColor"
        :rounded="roundedIcon"
      />
    </div>
    <div class="presentation__content">
      <div class="presentation__title">{{ title }}</div>
      <div v-if="subtitle" class="presentation__subtitle">{{ subtitle }}</div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'Presentation',
  props: {
    initials: {
      type: String,
      required: false,
      default: '',
    },
    icon: {
      type: String,
      required: false,
      default: '',
    },
    iconSize: {
      type: String,
      required: false,
      default: 'large',
    },
    roundedIcon: {
      type: Boolean,
      required: false,
      default: true,
    },
    image: {
      type: String,
      required: false,
      default: null,
    },
    avatarColor: {
      type: String,
      required: false,
      default: 'blue',
    },
    title: {
      type: String,
      default: '',
    },
    subtitle: {
      type: String,
      required: false,
      default: '',
    },
  },
  emits: ['click'],
}
</script>
