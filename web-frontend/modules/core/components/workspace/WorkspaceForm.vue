<template>
  <form @submit.prevent="submit">
    <FormGroup small-label :error="v$.name.$error" required>
      <template #label>
        <i class="iconoir-text"></i>
        {{ $t('workspaceForm.nameLabel') }}
      </template>

      <FormInput
        ref="name"
        v-model="v$.name.$model"
        :error="v$.name.$error"
        size="large"
        @focus.once="$event.target.select()"
        @blur="v$.name.$touch"
      ></FormInput>

      <template #error>{{ $t('error.requiredField') }}</template>
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
