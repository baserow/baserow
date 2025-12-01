<template>
  <form @submit.prevent="submit">
    <FormGroup
      :label="$t('apiTokenForm.nameLabel')"
      small-label
      required
      :error="fieldHasErrors('name')"
      class="margin-bottom-2"
    >
      <FormInput
        ref="name"
        v-model="v$.values.name.$model"
        size="large"
        :error="fieldHasErrors('name')"
        @blur="v$.values.name.$touch()"
      >
      </FormInput>

      <template #error> {{ v$.values.name.$errors[0]?.$message }}</template>
    </FormGroup>

    <FormGroup
      :error="fieldHasErrors('workspace')"
      small-label
      :label="$t('apiTokenForm.workspaceLabel')"
      required
      class="margin-bottom-2"
    >
      <Dropdown
        v-model="v$.values.workspace.$model"
        class="col-4"
        size="large"
        @hide="v$.values.workspace.$touch"
      >
        <DropdownItem
          v-for="workspace in workspaces"
          :key="workspace.id"
          :name="workspace.name"
          :value="workspace.id"
        ></DropdownItem>
      </Dropdown>

      <template #error>
        {{ v$.values.workspace.$errors[0]?.$message }}
      </template>
    </FormGroup>

    <slot></slot>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { mapState } from 'vuex'
import { required, helpers } from '@vuelidate/validators'

import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'APITokenForm',
  mixins: [form],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      values: {
        name: '',
        workspace: '',
      },
    }
  },
  computed: {
    ...mapState({
      workspaces: (state) => state.workspace.items,
    }),
  },
  mounted() {
    this.$refs.name.focus()
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
        workspace: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
      },
    }
  },
}
</script>
