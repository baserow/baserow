<template>
  <div v-if="hasRoles">
    <RoleSelectorButton
      :icon="selectedRole?.icon"
      :role-name="selectedRole?.name || row.permissions"
      @click="$refs.editRoleContext.toggle($event.currentTarget)"
    />
    <EditRoleContext
      ref="editRoleContext"
      :subject="row"
      :roles="roles"
      :workspace="workspace"
      :show-commercial-info="false"
      @update-role="$emit('update-link-role', { row, uid: $event.uid })"
    />
  </div>
  <div
    v-else
    v-tooltip:[tooltipOptions]="roleHelpText"
    class="invitation-link-role-field"
  >
    <RoleSelectorButton
      :icon="fixedRole?.icon"
      :role-name="fixedRole?.name || $t('inviteModal.linkNoRole')"
      read-only
    />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import RoleSelectorButton from '@baserow/modules/core/components/settings/RoleSelectorButton'
import EditRoleContext from '@baserow/modules/core/components/settings/members/EditRoleContext'

/**
 * The role an invitation link grants, which can be changed for targets with
 * roles to choose from. Targets that give their own role, like a team, show it
 * read-only with where it comes from.
 */
const props = defineProps({
  row: { type: Object, required: true },
  column: { type: Object, required: true },
})
defineEmits(['update-link-role'])

// The help text is a full sentence, which wraps instead of running on one line.
const tooltipOptions = { contentClasses: ['tooltip__content--expandable'] }

const workspace = computed(() => props.column.additionalProps.workspace)
const roles = computed(() =>
  props.row.targetType.getRoles(workspace.value, props.row.target)
)
const hasRoles = computed(() => roles.value.length > 0)
const selectedRole = computed(() =>
  roles.value.find(({ uid }) => uid === props.row.permissions)
)
const fixedRole = computed(() =>
  props.row.targetType.getInvitationLinkRole(workspace.value, props.row.target)
)
const roleHelpText = computed(() =>
  props.row.targetType.getInvitationLinkRoleHelpText(
    workspace.value,
    props.row.target
  )
)
</script>
