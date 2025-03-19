<template>
  <form @submit.prevent="submit">
    <FormGroup small-label :error="fieldHasErrors('name')" required>
      <template #label>
        <i class="iconoir-text"></i>
        {{ $t('workspaceForm.nameLabel') }}
      </template>

      <FormInput
        ref="name"
        v-model="v$.values.name.$model"
        :error="fieldHasErrors('name')"
        size="large"
        @focus.once="$event.target.select()"
        @blur="v$.values.name.$touch"
      ></FormInput>

      <template #error>{{ $t('error.requiredField') }}</template>
    </FormGroup>
    <slot></slot>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required, helpers } from '@vuelidate/validators'

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
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      values: {
        name: this.defaultName,
      },
    }
  },
  validations() {
    return {
      values: {
        name: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
      },
    }
  },

  mounted() {
    this.$refs.name.focus()
  },
}
</script>
