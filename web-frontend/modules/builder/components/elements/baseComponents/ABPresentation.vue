<template>
  <div class="ab-presentation" @click="$emit('click', $event)">
    <div v-if="image || icon || initials" class="ab-presentation__avatar">
      <ABAvatar
        :icon="icon"
        :image="image"
        :initials="initials"
        size="x-large"
        v-bind="$attrs"
      />
    </div>
    <div class="ab-presentation__content">
      <div class="ab-presentation__title">{{ title }}</div>
      <div v-if="subtitle" class="ab-presentation__subtitle">
        {{ subtitle }}
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ABPresentation',
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
      required: true,
      default: '',
    },
    subtitle: {
      type: String,
      required: false,
      default: '',
    },
  },
}
</script>
