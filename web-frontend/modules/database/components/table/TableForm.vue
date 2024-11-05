<template>
  <form @submit.prevent="submit">
    <FormGroup
      :error="fieldHasErrors('name')"
      required
      small-label
      class="margin-bottom-2"
    >
      <template #label>
        <i class="iconoir-text"></i> {{ $t('tableForm.name') }}</template
      >
      <FormInput
        ref="name"
        v-model="values.name"
        size="large"
        :error="fieldHasErrors('name')"
        @focus.once="$event.target.select()"
        @blur="v$.values.name.$touch()"
      >
      </FormInput>
      <template #error>
        {{ $t('error.requiredField') }}
      </template>
    </FormGroup>
    <slot></slot>
  </form>
</template>

<script>
import { required } from '@vuelidate/validators'

import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'TableForm',
  mixins: [form],
  props: {
    defaultName: {
      type: String,
      required: false,
      default: '',
    },
  },
  data() {
    return {
      allowedValues: ['name'],
      values: {
        name: this.defaultName,
      },
    }
  },
  mounted() {
    this.$refs.name.focus()
  },
  validations: {
    values: {
      name: {
        // No object-shorthand here to access vm properties
        required: function (value) {
          return required(value)
        },
      },
    },
  },
}
</script>
