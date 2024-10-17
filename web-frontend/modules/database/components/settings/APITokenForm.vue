<template>
  <form @submit.prevent="submit" @keydown.enter="submit">
    <FormGroup
      :label="$t('apiTokenForm.nameLabel')"
      small-label
      required
      :error="fieldHasErrors('name')"
      class="margin-bottom-2"
    >
      <FormInput
        ref="name"
        v-model="values.name"
        size="large"
        :error="fieldHasErrors('name')"
      >
      </FormInput>

      <template #error> {{ $t('error.requiredField') }}</template>
    </FormGroup>

    <FormGroup
      :error="fieldHasErrors('workspace')"
      small-label
      :label="$t('apiTokenForm.workspaceLabel')"
      required
      class="margin-bottom-2"
    >
      <Dropdown
        v-model="values.workspace"
        class="col-4"
        fixed-items
        @hide="$v.values.workspace.$touch()"
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
import { mapState } from 'vuex'
import { required } from 'vuelidate/lib/validators'

import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'APITokenForm',
  mixins: [form],
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
  validations: {
    values: {
      name: { required },
      workspace: { required },
    },
  },
}
</script>
