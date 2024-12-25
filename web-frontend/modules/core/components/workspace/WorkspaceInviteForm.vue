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
            @blur="$v.values.email.$touch()"
          >
          </FormInput>

          <template #error>
            {{ $t('workspaceInviteForm.errorInvalidEmail') }}
          </template>
        </FormGroup>
      </div>
      <div class="col col-5">
        <FormGroup>
          <div class="workspace-invite-form__role-selector">
            <slot name="roleSelectorLabel"></slot>
            <Dropdown
              v-model="values.permissions"
              class="workspace-invite-form__role-selector-dropdown"
              :show-search="false"
              fixed-items
            >
              <DropdownItem
                v-for="(role, index) in roles"
                :key="index"
                :ref="'role' + role.uid"
                :name="role.name"
                :value="role.uid"
                :disabled="role.isDeactivated"
                :description="role.description"
                @click="clickOnDeactivatedItem($event)"
              >
                {{ role.name }}
                <Badge
                  v-if="role.showIsBillable && role.isBillable"
                  color="cyan"
                  size="small"
                  bold
                  >{{ $t('common.billable') }}
                </Badge>
                <Badge
                  v-else-if="
                    role.showIsBillable &&
                    !role.isBillable &&
                    atLeastOneBillableRole
                  "
                  color="yellow"
                  size="small"
                  bold
                  class="margin-left-1"
                  >{{ $t('common.free') }}
                </Badge>
                <i v-if="role.isDeactivated" class="iconoir-lock"></i>
                <component
                  :is="deactivatedClickModal(role)"
                  :ref="'deactivatedClickModal-' + role.uid"
                  :v-if="deactivatedClickModal(role)"
                  :name="$t('workspaceInviteForm.additionalRoles')"
                  :workspace="workspace"
                ></component>
              </DropdownItem>
            </Dropdown>
          </div>
        </FormGroup>
      </div>
      <div class="col col-12 margin-top-2 margin-bottom-2">
        <FormGroup :error="fieldHasErrors('message')">
          <FormInput
            ref="message"
            v-model="values.message"
            :error="fieldHasErrors('message')"
            :placeholder="$t('workspaceInviteForm.optionalMessagePlaceholder')"
          ></FormInput>

          <template #error>
            {{
              $t('workspaceInviteForm.errorTooLongMessage', {
                amount: messageMaxLength,
              })
            }}
          </template>
        </FormGroup>
      </div>
      <slot></slot>
    </div>
  </form>
</template>

<script>
import { required, email, maxLength } from 'vuelidate/lib/validators'

import form from '@baserow/modules/core/mixins/form'

const MESSAGE_MAX_LENGTH = 250

export default {
  name: 'WorkspaceInviteForm',
  mixins: [form],
  props: {
    workspace: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      loading: false,
      values: {
        email: '',
        permissions: '',
        message: '',
      },
    }
  },
  computed: {
    messageMaxLength() {
      return MESSAGE_MAX_LENGTH
    },
    roles() {
      return this.workspace._.roles.filter((role) => role.isVisible)
    },
    defaultRole() {
      const activeRoles = this.roles.filter((role) => !role.isDeactivated)
      return activeRoles.length > 0 ? activeRoles[activeRoles.length - 1] : null
    },
    atLeastOneBillableRole() {
      return this.roles.some((role) => role.isBillable)
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
  methods: {
    deactivatedClickModal(role) {
      const allRoles = Object.values(this.$registry.getAll('roles'))
      return allRoles
        .find((r) => r.getUid() === role.uid)
        .getDeactivatedClickModal()
    },
    clickOnDeactivatedItem(value) {
      const role = this.roles.find((role) => role.uid === value)
      if (role && role.isDeactivated) {
        this.$refs[`deactivatedClickModal-${value}`][0].show()
      }
    },
  },
  validations: {
    values: {
      email: { required, email },
      message: { maxLength: maxLength(MESSAGE_MAX_LENGTH) },
    },
  },
}
</script>
