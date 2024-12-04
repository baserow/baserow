<template>
  <form @submit.prevent="submit">
    <FormGroup
      :error="v$.name.$error"
      required
      small-label
      class="margin-bottom-2"
    >
      <template #label>
        <i class="iconoir-text"></i> {{ $t('tableForm.name') }}</template
      >
      <FormInput
        ref="name"
        v-model="v$.name.$model"
        size="large"
        :error="v$.name.$error"
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
      values: null,
      v$: null,
    }
  },
  created() {
    const values = reactive({
      name: this.defaultName,
    })

    const rules = computed(() => ({
      name: {
        required,
      },
    }))
    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
  mounted() {
    this.$refs.name.focus()
  },
}
</script>
