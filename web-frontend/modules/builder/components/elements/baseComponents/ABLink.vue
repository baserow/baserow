<template>
  <a
    :class="[
      {
        'ab-link': variant !== 'button',
        'ab-button ab-button--medium': variant === 'button',
        'ab-button--full-width': variant === 'button' && fullWidth === true,
      },
      forceActiveClass,
    ]"
    :target="`_${target}`"
    :href="url"
    :rel="isExternalLink ? 'noopener noreferrer' : null"
    v-on="$listeners"
    @click="handleClick"
  >
    <slot></slot>
  </a>
</template>

<script>
/**
 * @typedef ABLink
 */

export default {
  name: 'ABLink',
  inject: ['mode'],
  props: {
    /**
     * @type {string} - The variant of the link. Can be `link` (default) or `button`.
     */
    variant: {
      type: String,
      required: false,
      default: 'link',
      validator(value) {
        return ['link', 'button'].includes(value)
      },
    },
    /**
     * @type {Boolean} - Wheter the button should be full width.
     */
    fullWidth: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * @type {string} - The target of the link. Can be `self` (default) or `blank`.
     */
    target: {
      type: String,
      required: false,
      default: 'self',
      validator(value) {
        return ['self', 'blank'].includes(value)
      },
    },
    /**
     * @type {string} - The URL of the link.
     */
    url: {
      type: String,
      required: true,
    },
    /**
     * @type {Boolean} - Whether the active class should be applied to the link.
     */
    forceActive: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  computed: {
    isExternalLink() {
      return !this.url.startsWith('/')
    },
    forceActiveClass() {
      return this.forceActive ? `ab-${this.variant}--force-active` : ''
    },
  },
  methods: {
    handleClick(event) {
      if (this.mode === 'editing' || !this.url) {
        event.preventDefault()
        return
      }
      if (this.target === 'self' && this.url.startsWith('/')) {
        event.preventDefault()
        if (this.$route.path !== this.url) {
          this.$router.push(this.url)
        }
      }
    },
  },
}
</script>
