<template>
  <form @submit.prevent="submit">
    <h3>{{ $t('workspaceInviteForm.invitationFormTitle') }}</h3>
    <div class="row">
      <div class="col col-7">
        <FormGroup small-label :error="fieldHasErrors('email')">
          <FormInput
            ref="email"
            v-model="values.email"
            :error="fieldHasErrors('email')"
            @blur="v$.values.email.$touch"
          >
          </FormInput>

          <template #error>
            {{ v$.values.email.$errors[0]?.$message }}
          </template>
        </FormGroup>
      </div>
      <div class="col col-5">
        <FormGroup :error="v$.values.permissions.$error">
          <div class="workspace-invite-form__role-selector">
            <slot name="roleSelectorLabel"></slot>
            <WorkspaceRoleSelector
              v-model="v$.values.permissions.$model"
              class="workspace-invite-form__role-selector-dropdown"
              :workspace="workspace"
              :roles="roles"
            />
          </div>
        </FormGroup>
      </div>
      <slot></slot>
    </div>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required, email, helpers } from '@vuelidate/validators'

import form from '@baserow/modules/core/mixins/form'
import WorkspaceRoleSelector from '@baserow/modules/core/components/workspace/WorkspaceRoleSelector'

export default {
  name: 'WorkspaceInviteForm',
  components: { WorkspaceRoleSelector },
  mixins: [form],
  props: {
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
      loading: false,
      values: {
        email: '',
        permissions: '',
      },
    }
  },
  computed: {
    roles() {
      return this.workspace._.roles.filter((role) => role.isVisible)
    },
    defaultRole() {
      const activeRoles = this.roles.filter((role) => !role.isDeactivated)
      return activeRoles.length > 0 ? activeRoles[activeRoles.length - 1] : null
    },
  },
  watch: {
    defaultRole: {
      handler(role) {
        this.values.permissions = role.uid
      },
      immediate: true,
    },
  },
  validations() {
    return {
      values: {
        email: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          email: helpers.withMessage(
            this.$t('workspaceInviteForm.errorInvalidEmail'),
            email
          ),
        },
        permissions: {},
      },
    }
  },
}
</script>
