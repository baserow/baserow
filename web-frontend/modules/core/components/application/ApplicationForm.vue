<template>
  <form @submit.prevent="submit">
    <FormGroup
      :error="v$.values.name.$error"
      small-label
      :label="$t('applicationForm.nameLabel')"
      required
    >
      <FormInput
        ref="name"
        v-model="v$.values.name.$model"
        size="large"
        :error="v$.values.name.$error"
        @focus.once="$event.target.select()"
        @blur="v$.values.name.$touch"
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
import { useVuelidate } from '@vuelidate/core'
import { required } from '@vuelidate/validators'
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
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
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
  validations() {
    return {
      values: {
        name: { required },
      },
    }
  },
}
</script>
