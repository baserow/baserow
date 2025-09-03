<template>
  <div class="auth-code-input">
    <input
      v-model="number1"
      type="text"
      maxlength="1"
      inputmode="numeric"
      class="auth-code-input__input"
      :class="{ 'auth-code-input__input--filled': number1 }"
      @keyup="handleKeyUp"
    />
    <input
      v-model="number2"
      type="text"
      maxlength="1"
      inputmode="numeric"
      class="auth-code-input__input"
      :class="{ 'auth-code-input__input--filled': number2 }"
      @keyup="handleKeyUp"
    />
    <input
      v-model="number3"
      type="text"
      maxlength="1"
      inputmode="numeric"
      class="auth-code-input__input"
      :class="{ 'auth-code-input__input--filled': number3 }"
      @keyup="handleKeyUp"
    />
    <input
      v-model="number4"
      type="text"
      maxlength="1"
      inputmode="numeric"
      class="auth-code-input__input"
      :class="{ 'auth-code-input__input--filled': number4 }"
      @keyup="handleKeyUp"
    />
    <input
      v-model="number5"
      type="text"
      maxlength="1"
      inputmode="numeric"
      class="auth-code-input__input"
      :class="{ 'auth-code-input__input--filled': number5 }"
      @keyup="handleKeyUp"
    />
    <input
      v-model="number6"
      type="text"
      maxlength="1"
      inputmode="numeric"
      class="auth-code-input__input"
      :class="{ 'auth-code-input__input--filled': number6 }"
      @keyup="handleKeyUp"
    />
  </div>
</template>

<script>
export default {
  name: 'AuthCodeInput',
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
  methods: {
    sanitizeInput(value) {
      const sanitized = value.replace(/\D/g, '').slice(0, 1)
      return sanitized
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

        if (this.allFilled) {
          this.$emit('all-filled', this.code)
        }
      }
    },
  },
}
</script>
