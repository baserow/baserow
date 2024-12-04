<template>
  <form @submit.prevent="submit">
    <FormGroup
      small-label
      :label="$t('accountForm.nameLabel')"
      required
      :error="v$.first_name.$error"
      class="margin-bottom-2"
    >
      <FormInput
        ref="first_name"
        v-model="v$.first_name.$model"
        size="large"
        :error="v$.first_name.$error"
        @blur="v$.first_name.$touch"
      ></FormInput>

      <template #error>
        <span v-if="v$.first_name.required.$invalid">
          {{ $t('error.requiredField') }}
        </span>
        <spam v-if="hasMinMaxError">
          {{
            $t('error.minMaxLength', {
              max: v$.first_name.maxLength.$params.max,
              min: v$.first_name.minLength.$params.min,
            })
          }}
        </spam>
      </template>
    </FormGroup>

    <FormGroup :label="$t('accountForm.languageLabel')" small-label required>
      <Dropdown v-model="v$.language.$model" :show-search="false" size="large">
        <DropdownItem
          v-for="locale in $i18n.locales"
          :key="locale.code"
          :name="locale.name"
          :value="locale.code"
        ></DropdownItem>
      </Dropdown>
    </FormGroup>

    <slot></slot>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import { required, maxLength, minLength } from '@vuelidate/validators'

import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'AccountForm',
  mixins: [form],
  data() {
    return {
      allowedValues: ['first_name', 'language'],
      values: null,
      v$: null,
    }
  },
  computed: {
    hasMinMaxError() {
      return (
        this.v$.first_name.maxLength.$invalid ||
        this.v$.first_name.minLength.$invalid
      )
    },
  },
  created() {
    const values = reactive({
      first_name: '',
      language: '',
    })

    const rules = computed(() => ({
      first_name: {
        required,
        minLength: minLength(2),
        maxLength: maxLength(150),
      },
      language: {
        required,
      },
    }))
    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
}
</script>
