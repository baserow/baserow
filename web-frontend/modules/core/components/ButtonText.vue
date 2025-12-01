<template>
  <component
    :is="tag === 'a' || href ? 'a' : 'button'"
    class="button-text"
    :class="classes"
    :disabled="disabled || loading"
    v-bind.prop="customBind"
    v-on="$listeners"
  >
    <i v-if="icon !== '' && !loading" class="button-text__icon" :class="icon" />
    <img v-else-if="image" alt="" :src="image" class="button-text__image" />

    <i v-if="loading" class="button-text__spinner"></i>
    <span v-if="$slots.default" class="button-text__label"><slot /></span>
  </component>
</template>

<script>
export default {
  props: {
    /**
     * The tag to use for the root element.
     */
    tag: {
      required: false,
      type: String,
      default: 'button',
      validator(value) {
        return ['a', 'button'].includes(value)
      },
    },
    /**
     * The size of the button. Available sizes are `regular` and `small`.
     */
    size: {
      required: false,
      type: String,
      default: 'regular',
      validator(value) {
        return ['regular', 'small'].includes(value)
      },
    },
    /**
     * The type of the button. Available types are `primary` and `secondary`.
     */
    type: {
      required: false,
      type: String,
      default: 'primary',
      validator(value) {
        return ['primary', 'secondary'].includes(value)
      },
    },
    /**
     * The icon of the button. Must be a valid iconoir or baserow icon class name.
     */
    icon: {
      required: false,
      type: String,
      default: '',
    },
    /**
     * The image of the button. If no icon is provided, this image will be shown.
     */
    image: {
      required: false,
      type: String,
      default: null,
    },
    /**
     * If true a loading icon will be shown.
     */
    loading: {
      required: false,
      type: Boolean,
      default: false,
    },
    /**
     * If true the button will be disabled.
     */
    disabled: {
      required: false,
      type: Boolean,
      default: false,
    },
    /**
     * If the button is a link, this is the href.
     */
    href: {
      required: false,
      type: String,
      default: null,
    },
    /**
     * If the button is a link, this is the rel. Available values are: nofollow, noopener, noreferrer.
     */
    rel: {
      required: false,
      type: String,
      default: null,
      validator(value) {
        const validRelValues = ['nofollow', 'noopener', 'noreferrer']
        const relValues = value.split(' ')

        return relValues.every((relValue) => validRelValues.includes(relValue))
      },
    },
    /**
     * If the button is a link, this is the target. Available values are: _blank, _self, _parent, _top.
     */
    target: {
      required: false,
      type: String,
      default: null,
      validator(value) {
        return ['_blank', '_self', '_parent', '_top'].includes(value)
      },
    },
  },
  computed: {
    classes() {
      const classObj = {
        [`button-text--${this.size}`]: this.size !== 'regular',
        [`button-text--${this.type}`]: this.type !== 'primary',
        'button-text--loading': this.loading,
      }
      return classObj
    },
    customBind() {
      const attr = {}
      if (this.tag === 'a') {
        attr.href = this.href
        attr.target = this.target
        attr.rel = this.rel
      }

      Object.keys(attr).forEach((key) => {
        if (attr[key] === null) {
          delete attr[key]
        }
      })

      return attr
    },
  },
}
</script>
