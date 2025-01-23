<template>
  <form @submit.prevent="submit">
    <FormGroup
      :error="fieldHasErrors('name')"
      small-label
      :label="$t('applicationForm.nameLabel')"
      required
    >
      <FormInput
        ref="name"
        v-model="values.name"
        size="large"
        :error="fieldHasErrors('name')"
        @focus.once="$event.target.select()"
        @blur="$v.values.name.$touch()"
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
import { required } from 'vuelidate/lib/validators'

import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'ApplicationForm',
  mixins: [form],
  props: {
    defaultName: {
      type: String,
      required: false,
      default: '',
    },
    loading: {
      type: Boolean,
      required: true,
    },
    workspace: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      values: {
        name: this.defaultValues.name,
      },
    }
  },
  mounted() {
    this.$refs.name.focus()
  },
  validations: {
    values: {
      name: { required },
    },
  },
}
</script>
