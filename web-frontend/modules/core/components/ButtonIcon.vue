<template>
  <button
    v-if="tag === 'button'"
    class="button-icon"
    :class="classes"
    :disabled="disabled"
    v-bind="customBind"
    :to="to"
  >
    <i v-if="!loading" class="button-icon__icon" :class="icon" />
  </button>
  <component
    :is="tag"
    v-else
    class="button-icon"
    :class="classes"
    :disabled="disabled"
    v-bind="customBind"
    :to="to"
  >
    <i v-if="!loading" class="button-icon__icon" :class="icon" />
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
     * The type of the button.
     */
    type: {
      required: false,
      type: String,
      default: 'primary',
      validator: function (value) {
        return ['primary', 'secondary'].includes(value)
      },
    },
    /**
     * The size of the button.
     */
    size: {
      required: false,
      type: String,
      default: 'regular',
      validator: function (value) {
        return ['regular', 'small'].includes(value)
      },
    },
    /**
     * The icon of the button.
     */
    icon: {
      required: false,
      type: String,
      default: '',
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
      default: undefined,
    },
    /**
     * If true the button will be disabled.
     */
    active: {
      required: false,
      type: Boolean,
      default: false,
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
        'button-icon--loading': this.loading,
        'button-icon--secondary': this.type === 'secondary',
        'button-icon--small': this.size === 'small',
        active: this.active,
      }
      return classObj
    },
    customBind() {
      const attr = { ...this.$attrs }
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
}
</script>
