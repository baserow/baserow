<template>
  <div class="auth-code-input">
    <input
      v-model="values.number1"
      type="text"
      maxlength="1"
      inputmode="numeric"
      class="auth-code-input__input"
      :class="{ 'auth-code-input__input--filled': values.number1 }"
      @keyup="handleKeyUp"
    />
    <input
      v-model="values.number2"
      type="text"
      maxlength="1"
      inputmode="numeric"
      class="auth-code-input__input"
      :class="{ 'auth-code-input__input--filled': values.number2 }"
      @keyup="handleKeyUp"
    />
    <input
      v-model="values.number3"
      type="text"
      maxlength="1"
      inputmode="numeric"
      class="auth-code-input__input"
      :class="{ 'auth-code-input__input--filled': values.number3 }"
      @keyup="handleKeyUp"
    />
    <input
      v-model="values.number4"
      type="text"
      maxlength="1"
      inputmode="numeric"
      class="auth-code-input__input"
      :class="{ 'auth-code-input__input--filled': values.number4 }"
      @keyup="handleKeyUp"
    />
    <input
      v-model="values.number5"
      type="text"
      maxlength="1"
      inputmode="numeric"
      class="auth-code-input__input"
      :class="{ 'auth-code-input__input--filled': values.number5 }"
      @keyup="handleKeyUp"
    />
    <input
      v-model="values.number6"
      type="text"
      maxlength="1"
      inputmode="numeric"
      class="auth-code-input__input"
      :class="{ 'auth-code-input__input--filled': values.number6 }"
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
  methods: {
    handleKeyUp(event) {

    }
  }
}
</script>
