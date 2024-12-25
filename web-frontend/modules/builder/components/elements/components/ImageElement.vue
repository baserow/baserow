<template>
  <div
    :class="classes"
    class="image-element"
    :style="getStyleOverride('image')"
  >
    <ABImage
      :alt="
        element.alt_text
          ? resolvedAltText ||
            (mode === 'editing' ? $t('imageElement.emptyValue') : '')
          : $t('imageElement.missingValue')
      "
      :src="imageSource"
    />
  </div>
</template>

<script>
import element from '@baserow/modules/builder/mixins/element'
import { IMAGE_SOURCE_TYPES } from '@baserow/modules/builder/enums'
import { ensureString } from '@baserow/modules/core/utils/validator'

export default {
  name: 'ImageElement',
  mixins: [element],
  props: {
    /**
     * @type {Object}
     * @property {string} image_source_type - If the image is uploaded or has a url
     * @property {Object} image_file - The image file uploaded (optional)
     * @property {string} image_url - The url of the image source (optional)
     * @property {string} alt_text - The text that's displayed when the image can't load
     */
    element: {
      type: Object,
      required: true,
    },
  },
  computed: {
    imageSource() {
      return this.element.image_source_type === IMAGE_SOURCE_TYPES.UPLOAD
        ? this.element.image_file?.url
        : this.resolvedURL
    },
    resolvedAltText() {
      return ensureString(this.resolveFormula(this.element.alt_text))
    },
    resolvedURL() {
      return ensureString(this.resolveFormula(this.element.image_url))
    },
    classes() {
      return {
        'element--no-value': !this.imageSource && !this.resolvedAltText,
      }
    },
  },
}
</script>
