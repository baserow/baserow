<template>
  <div
    class="auth-code-input"
    :class="{ 'auth-code-input--full-width': fullWidth }"
  >
    <input
      ref="input1"
      v-model="number1"
      type="text"
      maxlength="1"
      inputmode="numeric"
      class="auth-code-input__input"
      :class="{ 'auth-code-input__input--filled': allFilled }"
      @keyup="handleKeyUp"
      @keydown="handleKeyDown"
      @paste="pasteAt(1, $event)"
    />
    <input
      ref="input2"
      v-model="number2"
      type="text"
      maxlength="1"
      inputmode="numeric"
      class="auth-code-input__input"
      :class="{ 'auth-code-input__input--filled': allFilled }"
      @keyup="handleKeyUp"
      @keydown="handleKeyDown"
      @paste="pasteAt(2, $event)"
    />
    <input
      ref="input3"
      v-model="number3"
      type="text"
      maxlength="1"
      inputmode="numeric"
      class="auth-code-input__input"
      :class="{ 'auth-code-input__input--filled': allFilled }"
      @keyup="handleKeyUp"
      @keydown="handleKeyDown"
      @paste="pasteAt(3, $event)"
    />
    <input
      ref="input4"
      v-model="number4"
      type="text"
      maxlength="1"
      inputmode="numeric"
      class="auth-code-input__input"
      :class="{ 'auth-code-input__input--filled': allFilled }"
      @keyup="handleKeyUp"
      @keydown="handleKeyDown"
      @paste="pasteAt(4, $event)"
    />
    <input
      ref="input5"
      v-model="number5"
      type="text"
      maxlength="1"
      inputmode="numeric"
      class="auth-code-input__input"
      :class="{ 'auth-code-input__input--filled': allFilled }"
      @keyup="handleKeyUp"
      @keydown="handleKeyDown"
      @paste="pasteAt(5, $event)"
    />
    <input
      ref="input6"
      v-model="number6"
      type="text"
      maxlength="1"
      inputmode="numeric"
      class="auth-code-input__input"
      :class="{ 'auth-code-input__input--filled': allFilled }"
      @keyup="handleKeyUp"
      @keydown="handleKeyDown"
      @paste="pasteAt(6, $event)"
    />
  </div>
</template>

<script>
export default {
  name: 'AuthCodeInput',
  props: {
    fullWidth: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['all-filled'],
  data() {
    return {
      values: {
        number1: '',
        number2: '',
        number3: '',
        number4: '',
        number5: '',
        number6: '',
      },
      hasEmitted: false,
    }
  },
  computed: {
    number1: {
      get() {
        return this.values.number1
      },
      set(value) {
        this.values.number1 = this.sanitizeInput(value)
      },
    },
    number2: {
      get() {
        return this.values.number2
      },
      set(value) {
        this.values.number2 = this.sanitizeInput(value)
      },
    },
    number3: {
      get() {
        return this.values.number3
      },
      set(value) {
        this.values.number3 = this.sanitizeInput(value)
      },
    },
    number4: {
      get() {
        return this.values.number4
      },
      set(value) {
        this.values.number4 = this.sanitizeInput(value)
      },
    },
    number5: {
      get() {
        return this.values.number5
      },
      set(value) {
        this.values.number5 = this.sanitizeInput(value)
      },
    },
    number6: {
      get() {
        return this.values.number6
      },
      set(value) {
        this.values.number6 = this.sanitizeInput(value)
      },
    },
    code() {
      return (
        this.values.number1 +
        this.values.number2 +
        this.values.number3 +
        this.values.number4 +
        this.values.number5 +
        this.values.number6
      )
    },
    allFilled() {
      return this.code.length === 6
    },
  },
  watch: {
    allFilled(isFilled) {
      if (isFilled && !this.hasEmitted) {
        this.hasEmitted = true
        this.$emit('all-filled', this.code)
      }
      if (!isFilled) {
        this.hasEmitted = false
      }
    },
  },
  mounted() {
    this.reset()
  },
  methods: {
    focusIndex(i) {
      const el = this.$refs[`input${i}`]
      if (el && typeof el.focus === 'function') el.focus()
    },
    reset() {
      this.values.number1 = ''
      this.values.number2 = ''
      this.values.number3 = ''
      this.values.number4 = ''
      this.values.number5 = ''
      this.values.number6 = ''
      this.$refs.input1.focus()
      this.hasEmitted = false
    },
    sanitizeInput(value) {
      const sanitized = value.replace(/\D/g, '').slice(0, 1)
      return sanitized
    },
    handleKeyDown(event) {
      const input = event.target
      const value = input.value

      // Handle backspace - move to previous input if current is empty
      if (event.key === 'Backspace' && !value) {
        const previousInput = input.previousElementSibling
        if (previousInput && previousInput.tagName === 'INPUT') {
          previousInput.focus()
        }
      }
    },
    handleKeyUp(event) {
      const input = event.target
      const value = input.value
      const isDigit = /\d/g.test(value)

      // Auto-focus to next input when a digit is entered
      if (isDigit) {
        const nextInput = input.nextElementSibling
        if (nextInput && nextInput.tagName === 'INPUT') {
          nextInput.focus()
        }
      }
    },
    pasteAt(startIndex, event) {
      event.preventDefault()

      const raw =
        (event.clipboardData && event.clipboardData.getData('text')) ||
        (window.clipboardData && window.clipboardData.getData('Text')) ||
        ''

      const digits = raw.replace(/\D/g, '')
      const maxLen = 7 - startIndex
      const chunk = digits.slice(0, maxLen)

      for (let i = startIndex; i <= 6; i++) {
        this.values[`number${i}`] = ''
      }

      for (let offset = 0; offset < chunk.length; offset++) {
        const i = startIndex + offset
        this.values[`number${i}`] = chunk[offset]
      }

      const nextIndex = Math.min(startIndex + chunk.length, 6)
      this.$nextTick(() => this.focusIndex(nextIndex))
    },
  },
}
</script>
