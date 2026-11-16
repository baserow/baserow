<template>
  <div class="ab-image">
    <img
      class="ab-image__img"
      :alt="alt"
      :src="src"
      :loading="lazy ? 'lazy' : null"
      v-bind="imageAttributes"
    />
  </div>
</template>

<script>
/**
 * @typedef ABImage
 */

export default {
  name: 'ABImage',
  props: {
    /**
     * @type {String} - Alternative text to image.
     */
    alt: {
      type: String,
      required: false,
      default: '',
    },
    /**
     * @type {String} - Image url.
     */
    src: {
      type: String,
      required: false,
      default: '',
    },
    /**
     * @type {Boolean} - Whether the image should be loaded lazily.
     */
    lazy: {
      type: Boolean,
      required: false,
      default: true,
    },
    /**
     * @type {Object} - Extra attributes and listeners for the image itself, such
     * as the ones that make it clickable.
     */
    imageAttributes: {
      type: Object,
      required: false,
      default: () => ({}),
    },
  },
}
</script>
