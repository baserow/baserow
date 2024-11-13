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
        v-model="v$.name.$model"
        size="large"
        :error="fieldHasErrors('name')"
        @focus.once="$event.target.select()"
        @blur="v$.name.$touch"
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
import { reactive, computed } from 'vue'
import { required } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'ApplicationForm',
  mixins: [form],
  data() {
    return {
      values: null,
      v$: null,
    }
  },
  mounted() {
    this.$refs.name.focus()
  },
  created() {
    const values = reactive({
      name: this.defaultValues.name,
    })

    const rules = computed(() => ({
      name: { required },
    }))
    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
}
</script>
