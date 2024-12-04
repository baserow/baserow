<template>
  <form @submit.prevent="submit">
    <FormGroup
      :label="$t('apiTokenForm.nameLabel')"
      small-label
      required
      :error="v$.name.$error"
      class="margin-bottom-2"
    >
      <FormInput
        ref="name"
        v-model="v$.name.$model"
        size="large"
        :error="v$.name.$error"
        @blur="v$.name.$touch"
      >
      </FormInput>

      <template #error> {{ $t('error.requiredField') }}</template>
    </FormGroup>

    <FormGroup
      :error="v$.workspace.$error"
      small-label
      :label="$t('apiTokenForm.workspaceLabel')"
      required
      class="margin-bottom-2"
    >
      <Dropdown
        v-model="v$.workspace.$model"
        class="col-4"
        @hide="v$.workspace.$touch"
      >
        <DropdownItem
          v-for="workspace in workspaces"
          :key="workspace.id"
          :name="workspace.name"
          :value="workspace.id"
        ></DropdownItem>
      </Dropdown>

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
import { mapState } from 'vuex'
import { required } from '@vuelidate/validators'

import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'APITokenForm',
  mixins: [form],
  data() {
    return {
      values: null,
      v$: null,
    }
  },
  computed: {
    ...mapState({
      workspaces: (state) => state.workspace.items,
    }),
  },
  created() {
    const values = reactive({
      name: '',
      workspace: '',
    })

    const rules = computed(() => ({
      name: { required },
      workspace: { required },
    }))
    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
  mounted() {
    this.$refs.name.focus()
  },
}
</script>
