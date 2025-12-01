<template>
  <textarea
    v-if="multiline === true"
    ref="textarea"
    class="ab-input"
    style="resize: none"
    :value="fromValue(value)"
    :placeholder="placeholder"
    :rows="rows"
    @blur="$emit('blur', $event)"
    @input="$emit('input', toValue($event.target.value))"
    @focus="$emit('focus', $event)"
    @click="$emit('click', $event)"
    @keydown="$emit('keydown', $event)"
  ></textarea>
  <input
    v-else
    ref="input"
    :type="type"
    class="ab-input"
    :value="fromValue(value)"
    :placeholder="placeholder"
    @blur="$emit('blur', $event)"
    @input="$emit('input', toValue($event.target.value))"
    @focus="$emit('focus', $event)"
    @click="$emit('click', $event)"
    @keydown="$emit('keydown', $event)"
  />
</template>

<script>
export default {
  name: 'ABInput',
  model: {
    prop: 'value',
    event: 'input',
  },
  props: {
    /**
     * @type {string} - The value of the input.
     */
    value: {
      type: [String, Number],
      required: false,
      default: '',
    },
    /**
     * @type {string} - The placeholder value of the input.
     */
    placeholder: {
      type: String,
      required: false,
      default: null,
    },
    /**
     * @type {Function} - The function to process user input before storing it.
     */
    toValue: {
      type: Function,
      required: false,
      default: (value) => value,
    },
    /**
     * @type {Function} - The function to process/convert the value to a string.
     */
    fromValue: {
      type: Function,
      required: false,
      default: (value) => value,
    },
    /**
     * @type {boolean} - Whether the input is multiline.
     */
    multiline: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * @type {number} - The number of rows (height) of the input.
     */
    rows: {
      type: Number,
      required: false,
      default: 3,
    },
    /**
     * @type {string} - Input type. Can be `text` (default) or `password`. (only for single line inputs)
     */
    type: {
      type: String,
      required: false,
      default: 'text',
      validator(value) {
        return ['text', 'password'].includes(value)
      },
    },
  },
  watch: {
    value: {
      async handler(value) {
        await this.$nextTick()
        this.updateTextareaHeight()
      },
      immediate: true,
    },
    async rows(value) {
      await this.$nextTick()
      this.updateTextareaHeight()
    },
    async multiline(value) {
      await this.$nextTick()
      this.updateTextareaHeight()
    },
  },
  methods: {
    updateTextareaHeight() {
      if (this.multiline && this.$refs.textarea) {
        const textarea = this.$refs.textarea
        textarea.style.height = 'auto'
        textarea.style.height = `${textarea.scrollHeight + 2}px`
      }
    },
    focus() {
      if (this.multiline === true) {
        this.$refs.textarea.focus()
      } else {
        this.$refs.input.focus()
      }
    },
  },
}
</script>
