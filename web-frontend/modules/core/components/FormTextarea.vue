<template>
  <textarea
    ref="textarea"
    :value="fromValue(value)"
    class="form-textarea"
    :rows="autoExpandable ? minRows : rows"
    :placeholder="placeholder"
    :disabled="disabled"
    :maxlength="maxlength"
    :class="{
      'form-textarea--error': error,
      'form-textarea--disabled': disabled,
      'form-textarea--small': size === 'small',
      'form-textarea--auto-expendable': autoExpandable,
    }"
    :style="{
      overflow: textBoxOverflow ? textBoxOverflow : 'visible',
      ...heightStyle,
    }"
    @blur="$emit('blur', $event)"
    @focus="$emit('focus', $event)"
    @input="$emit('input', toValue($event.target.value))"
    @keyup="$emit('keyup', $event)"
    @keydown="$emit('keydown', $event)"
  ></textarea>
</template>

<script>
export default {
  name: 'FormTextarea',
  props: {
    /**
     * The number of rows to display.
     */
    rows: {
      type: Number,
      required: false,
      default: 12,
    },
    /**
     * The placeholder to display.
     */
    placeholder: {
      type: String,
      required: false,
      default: null,
    },
    /**
     * If true, the textarea will be disabled.
     */
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * If true, the textarea will be in an error state.
     */
    error: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * The value of the textarea.
     */
    value: {
      type: String,
      default: null,
    },
    toValue: {
      type: Function,
      required: false,
      default: (value) => value,
    },
    fromValue: {
      type: Function,
      required: false,
      default: (value) => value,
    },
    /**
     * If true, the textarea will automatically expand to fit the content.
     */
    autoExpandable: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * The maximum number of rows to display when autoExpandable is true.
     */
    maxRows: {
      required: false,
      type: Number,
      default: 4,
    },
    /**
     * The minimum number of rows to display when autoExpandable is true.
     */
    minRows: {
      required: false,
      type: Number,
      default: 1,
    },
    /**
     * The maximum length of the textarea.
     */
    maxlength: {
      required: false,
      type: Number,
      default: null,
    },
    /**
     * The size of the textarea.
     */
    size: {
      type: String,
      required: false,
      validator: function (value) {
        return ['regular', 'small'].includes(value)
      },
      default: 'regular',
    },
  },
  data() {
    return {
      numTextAreaLines: this.minRows,
      verticalPadding: 0,
    }
  },
  computed: {
    textBoxSize() {
      if (this.autoExpandable) {
        return (
          22 * Math.min(this.numTextAreaLines, this.maxRows) +
          this.verticalPadding
        )
      }
      return null
    },
    textBoxOverflow() {
      if (this.autoExpandable)
        return this.numTextAreaLines > this.maxRows ? 'auto' : 'hidden'
      return null
    },
    heightStyle() {
      if (this.textBoxSize) {
        return {
          height: `${this.textBoxSize}px`,
        }
      }
      return null
    },
  },
  watch: {
    value() {
      if (this.autoExpandable) this.resizeTextArea()
    },
  },
  mounted() {
    if (this.autoExpandable) this.resizeTextArea()
  },

  methods: {
    focus() {
      this.$refs.textarea.focus()
    },
    blur() {
      this.$refs.textarea.blur()
    },
    resizeTextArea() {
      this.$nextTick(() => {
        const textAreaElement = this.$refs.textarea
        this.numTextAreaLines = this.calculateHeight(textAreaElement)
      })
    },
    /**
     * Taken from https://stackoverflow.com/questions/1760629/how-to-get-number-of-rows-in-textarea-using-javascript/1761203#1761203
     *
     * The key reason we need this is to resize a fully expanded textarea to something
     * smaller as a user deletes newlines or text. Hence we need to actually manipulate
     * the dom and lower the height of the textarea until we find overflow is occurring
     * again to re-find the correct min height.
     */
    calculateContentHeight(ta, scanAmount) {
      const origHeight = ta.style.height
      let height = ta.offsetHeight
      const scrollHeight = ta.scrollHeight
      const overflow = ta.style.overflow
      /// only bother if the ta is bigger than content
      if (height >= scrollHeight) {
        /// check that our browser supports changing dimension
        /// calculations mid-way through a function call...
        ta.style.height = height + scanAmount + 'px'
        /// because the scrollbar can cause calculation problems
        ta.style.overflow = 'hidden'
        /// by checking that scrollHeight has updated
        if (scrollHeight < ta.scrollHeight) {
          /// now try and scan the ta's height downwards
          /// until scrollHeight becomes larger than height
          while (ta.offsetHeight >= ta.scrollHeight) {
            ta.style.height = (height -= scanAmount) + 'px'
          }
          /// be more specific to get the exact height
          while (ta.offsetHeight < ta.scrollHeight) {
            ta.style.height = height++ + 'px'
          }
          height--
          /// reset the ta back to it's original height
          ta.style.height = origHeight
          /// put the overflow back
          ta.style.overflow = overflow
          return height
        } else {
          // We weren't able to resize this element inside this function call to figure
          // out it's true height so we give up and just return the scrollHeight.
          return scrollHeight
        }
      } else {
        return scrollHeight
      }
    },
    calculateHeight(ta) {
      const style = window.getComputedStyle
        ? window.getComputedStyle(ta)
        : ta.currentStyle

      this.verticalPadding =
        parseInt(style.paddingTop.replace('px', '')) +
        parseInt(style.paddingBottom.replace('px', ''))

      // This will get the line-height only if it is set in the css,
      // otherwise it's "normal"
      const taLineHeight = parseInt(style.lineHeight, 10)
      // Get the scroll height of the textarea
      const taHeight =
        this.calculateContentHeight(ta, taLineHeight) - this.verticalPadding
      // calculate the number of lines
      return Math.ceil(taHeight / taLineHeight)
    },
  },
}
</script>
