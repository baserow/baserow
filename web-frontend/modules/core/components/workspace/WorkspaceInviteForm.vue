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
            <Dropdown
              v-model="v$.values.permissions.$model"
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
                  :is="
                    deactivatedClickModal(role)
                      ? deactivatedClickModal(role)[0]
                      : null
                  "
                  :ref="'deactivatedClickModal-' + role.uid"
                  :v-if="deactivatedClickModal(role)"
                  v-bind="
                    deactivatedClickModal(role)
                      ? deactivatedClickModal(role)[1]
                      : null
                  "
                  :workspace="workspace"
                ></component>
              </DropdownItem>
            </Dropdown>
          </div>
        </FormGroup>
      </div>
      <div class="col col-12 margin-top-2 margin-bottom-2">
        <FormGroup :error="v$.values.message.$error">
          <FormInput
            ref="message"
            v-model="v$.values.message.$model"
            :error="v$.values.message.$error"
            :placeholder="$t('workspaceInviteForm.optionalMessagePlaceholder')"
          ></FormInput>

          <template #error>
            {{ v$.values.message.$errors[0]?.$message }}
          </template>
        </FormGroup>
      </div>
      <slot></slot>
    </div>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required, email, maxLength, helpers } from '@vuelidate/validators'

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
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
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
        const ref = this.$refs[`deactivatedClickModal-${value}`]
        if (ref) {
          ref[0].show()
        }
      }
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
        message: {
          maxLength: helpers.withMessage(
            this.$t('workspaceInviteForm.errorTooLongMessage', {
              amount: this.messageMaxLength,
            }),
            maxLength(MESSAGE_MAX_LENGTH)
          ),
        },
        permissions: {},
      },
    }
  },
}
</script>
