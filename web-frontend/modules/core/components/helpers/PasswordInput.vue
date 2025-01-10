<!--
This helper component can only be used in a form which uses the password validation
from modules/core/validators.js
as ist expects the following vuelidate validation state params

- required
- maxLength
- minLength

In order to use this component in another component/form it needs a value
prop which can be passed via the 'v-model' directive. That means the state for the 
password value always lives in the parent component.
The parent component also needs to provide the vuelidate password validation in order
for this component to show all the possible validation errors.

Example Usage:

<PasswordInput
   v-model="PASSWORDSTATE"
   :validation-state="the vuelidate validation instance of the given password value"
/>

In case the password validation rules change, the passwordValidation object in the
validators file needs to be updated, as well as this component.

modules/core/validators.js

-->
<template>
  <FormGroup
    small-label
    :label="label"
    required
    :error="validationState.$error"
  >
    <FormInput
      :error="validationState.$error"
      type="password"
      size="large"
      :autocomplete="autocomplete"
      :value="value"
      :placeholder="placeholder"
      @blur="validationState.$touch"
      @input="$emit('input', $event)"
    >
    </FormInput>

    <template #error>
      <span v-if="validationState.$error && validationState.required.$invalid">
        <i v-if="showErrorIcon" class="iconoir-warning-triangle"></i>
        {{ $t('error.inputRequired') }}
      </span>
      <span v-if="validationState.$error && validationState.maxLength.$invalid">
        <i v-if="showErrorIcon" class="iconoir-warning-triangle"></i>
        {{
          $t('error.maxLength', {
            max: validationState.maxLength.$params.max,
          })
        }}
      </span>
      <span v-if="validationState.$error && validationState.minLength.$invalid">
        <i v-if="showErrorIcon" class="iconoir-warning-triangle"></i>
        {{
          $t('error.minLength', {
            min: validationState.minLength.$params.min,
          })
        }}
      </span>
    </template>
  </FormGroup>
</template>

<script>
export default {
  name: 'PasswordInput',
  props: {
    validationState: {
      type: Object,
      required: true,
    },
    value: {
      type: String,
      required: true,
    },
    label: {
      type: String,
      required: false,
      default: null,
    },
    autocomplete: {
      type: String,
      required: false,
      default: 'new-password',
    },
    placeholder: {
      type: String,
      required: false,
      default: null,
    },
    errorPlaceholderClass: {
      type: String,
      required: false,
      default: '',
    },
    showErrorIcon: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
}
</script>
