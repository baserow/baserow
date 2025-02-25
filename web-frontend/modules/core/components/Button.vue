<template>
  <component
    :is="tag"
    class="button"
    :class="classes"
    :disabled="disabled || loading"
    :to="to"
    v-bind.prop="customBind"
    v-on="$listeners"
  >
    <i v-if="icon" class="button__icon" :class="icon" />
    <span v-if="hasSlot" class="button__label"><slot></slot></span>
    <i v-if="appendIcon" class="button__icon" :class="appendIcon" />
  </component>
</template>

<script>
export default {
  props: {
    /**
     * The HTML tag to use for the button. Available tags are: a, button.
     */
    tag: {
      required: false,
      type: String,
      default: 'button',
      validator(value) {
        return ['a', 'button', 'nuxt-link'].includes(value)
      },
    },
    /**
     * The size of the button.
     */
    size: {
      required: false,
      type: String,
      default: 'regular',
      validator(value) {
        return ['small', 'regular', 'large', 'tiny', 'xlarge'].includes(value)
      },
    },
    /**
     * The type of the button. Available types are: primary, secondary, danger.
     */
    type: {
      required: false,
      type: String,
      default: 'primary',
      validator(value) {
        return ['primary', 'secondary', 'danger', 'upload', 'ghost'].includes(
          value
        )
      },
    },
    /**
     * The icon of the button. It will be displayed before the button label.
     */
    icon: {
      required: false,
      type: String,
      default: '',
    },
    /**
     * The icon of the button. It will be displayed after the button label.
     */
    appendIcon: {
      required: false,
      type: String,
      default: '',
    },
    /**
     * Wether the button is loading or not.
     */
    loading: {
      required: false,
      type: Boolean,
      default: false,
    },
    /**
     * Wether the button is active or not.
     */
    active: {
      required: false,
      type: Boolean,
      default: false,
    },
    /**
     * Wether the button is disabled or not.
     */
    disabled: {
      required: false,
      type: Boolean,
      default: false,
    },
    /**
     * Make the button full width.
     */
    fullWidth: {
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
    /**
     * If the button is a nuxt-link, this is the to attribute.
     */
    to: {
      type: Object,
      required: false,
      default: null,
    },
    /**
     * If the button is a link, this is the download attribute.
     */
    download: {
      required: false,
      type: String,
      default: null,
    },
  },
  computed: {
    hasSlot() {
      return !!this.$slots.default
    },
    classes() {
      const hasIcon = this.prependIcon || this.appendIcon || this.icon
      const classObj = {
        [`button--${this.size}`]: this.size,
        [`button--${this.type}`]: this.type,
        'button--primary': !this.type,
        'button--full-width': this.fullWidth,
        'button--icon-only': hasIcon && !this.$slots.default,
        'button--loading': this.loading,
        'button--overflow': this.overflow,
        'button--active': this.active,
      }
      return classObj
    },
    customBind() {
      const attr = {}
      if (this.tag === 'a') {
        attr.href = this.href
        attr.target = this.target
        attr.rel = this.rel
        attr.download = this.download
      }

      Object.keys(attr).forEach((key) => {
        if (attr[key] === null) {
          delete attr[key]
        }
      })

      return attr
    },
  },
  methods: {
    focus() {
      this.$el.focus()
    },
  },
}
</script>
