<template>
  <form @submit.prevent="submit">
    <FormGroup small-label :error="fieldHasErrors('name')" required>
      <template #label>
        <i class="iconoir-text"></i>
        {{ $t('workspaceForm.nameLabel') }}
      </template>

      <FormInput
        ref="name"
        v-model="values.name"
        :error="fieldHasErrors('name')"
        size="large"
        @focus.once="$event.target.select()"
        @blur="v$.values.name.$touch()"
      ></FormInput>

      <template #error>{{ $t('error.requiredField') }}</template>
    </FormGroup>
    <slot></slot>
  </form>
</template>

<script>
import { required } from '@vuelidate/validators'

import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'WorkspaceForm',
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
      values: {
        name: this.defaultName,
      },
    }
  },
  validations: {
    values: {
      name: { required },
    },
  },
  mounted() {
    this.$refs.name.focus()
  },
}
</script>
