<template>
  <Context overflow-scroll max-height-if-outside-viewport>
    <template v-if="Object.keys(subject).length > 0">
      <div class="context__menu-title">
        <div class="edit-role-context__header">
          <div>
            {{ $t('membersSettings.membersTable.columns.role') }}
          </div>
          <div
            v-if="atLeastOneBillableRole"
            class="edit-role-context__header-link"
          >
            <i class="iconoir-book"></i>
            <a
              href="https://baserow.io/user-docs/subscriptions-overview#who-is-considered-a-user-for-billing-purposes"
              target="_blank"
            >
              {{ $t('editRoleContext.billableRolesLink') }}
            </a>
          </div>
        </div>
      </div>
      <ul class="context__menu context__menu--can-be-active">
        <li
          v-for="(role, index) in visibleRoles"
          :key="index"
          class="context__menu-item"
        >
          <a
            class="context__menu-item-link context__menu-item-link--with-desc"
            :class="{
              active:
                !role.isDeactivated && subject[roleValueColumn] === role.uid,
              disabled: role.isDeactivated,
            }"
            @click="
              !role.isDeactivated
                ? roleUpdate(role.uid, subject)
                : clickOnDeactivatedItem(role.uid)
            "
          >
            <span class="context__menu-item-title">
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
                >{{ $t('common.free') }}
              </Badge>
              <i v-if="role.isDeactivated" class="iconoir-lock"></i>
            </span>
            <div v-if="role.description" class="context__menu-item-description">
              {{ role.description }}
            </div>
            <i
              v-if="
                !role.isDeactivated && subject[roleValueColumn] === role.uid
              "
              class="context__menu-active-icon iconoir-check"
            ></i>
          </a>
          <template v-if="deactivatedClickModal(role)">
            <component
              :is="deactivatedClickModal(role)[0]"
              :ref="'deactivatedClickModal-' + role.uid"
              v-bind="deactivatedClickModal(role)[1]"
              :name="$t('editRoleContext.additionalRoles')"
              :workspace="workspace"
            ></component>
          </template>
        </li>
        <li
          v-if="allowRemovingRole"
          class="context__menu-item context__menu-item--with-separator"
        >
          <a
            class="context__menu-item-link context__menu-item-link--delete"
            @click="$emit('delete')"
            >{{ $t('action.remove') }}</a
          >
        </li>
      </ul>
    </template>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'

export default {
  name: 'EditRoleContext',
  mixins: [context],
  props: {
    workspace: {
      type: Object,
      required: true,
    },
    subject: {
      required: true,
      type: Object,
    },
    roles: {
      required: true,
      type: Array,
    },
    roleValueColumn: {
      type: String,
      required: false,
      default: 'permissions',
    },
    allowRemovingRole: {
      type: Boolean,
      default: false,
    },
  },
  computed: {
    visibleRoles() {
      return this.roles.filter((role) => role.isVisible)
    },
    atLeastOneBillableRole() {
      return this.roles.some((role) => role.isBillable)
    },
  },
  methods: {
    roleUpdate(roleNew, subject) {
      if (subject[this.roleValueColumn] === roleNew) {
        return
      }

      this.$emit('update-role', { uid: roleNew, subject })
      this.hide()
    },
    deactivatedClickModal(role) {
      const allRoles = Object.values(this.$registry.getAll('roles'))
      return allRoles
        .find((r) => r.getUid() === role.uid)
        .getDeactivatedClickModal()
    },
    clickOnDeactivatedItem(value) {
      const ref = this.$refs[`deactivatedClickModal-${value}`]
      if (ref) {
        ref[0].show()
      }
    },
  },
}
</script>
