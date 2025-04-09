<template>
  <div
    class="ab-avatar"
    :class="{
      'ab-avatar--rounded': rounded,
      [`ab-avatar--${size}`]: true,
      [`ab-avatar--${color}`]: color && !image,
      'ab-avatar--transparent': image || color === 'transparent',
    }"
  >
    <i v-if="icon" :class="icon" class="ab-avatar__icon" />
    <img v-if="image" :src="image" class="ab-avatar__image" />
    <span v-if="initials && !image" class="ab-avatar__initials">{{
      initials
    }}</span>
  </div>
</template>

<script>
export default {
  name: 'ABAvatar',
  props: {
    /**
     * The icon classname to display.
     */
    icon: {
      type: String,
      required: false,
      default: null,
    },
    /**
     * The URL of the image to display.
     */
    image: {
      type: String,
      required: false,
      default: null,
    },
    /**
     * If true the avatar will be rounded.
     */
    rounded: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * The initials to display if no image is provided
     */
    initials: {
      type: String,
      required: false,
      default: null,
    },
    /**
     * The background color of the avatar
     */
    color: {
      required: false,
      type: String,
      default: 'neutral',
      validator(value) {
        return [null, undefined, 'neutral', 'transparent'].includes(value)
      },
    },
    /**
     * The size of the avatar
     */
    size: {
      type: String,
      required: false,
      default: 'medium',
      validator(value) {
        return ['small', 'medium', 'large', 'x-large'].includes(value)
      },
    },
  },
}
</script>
