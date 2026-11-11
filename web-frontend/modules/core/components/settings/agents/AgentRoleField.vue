<template>
  <div>
    <RoleSelectorButton
      :icon="selectedRole?.icon"
      :role-name="selectedRole?.name || row.role_uid"
      :read-only="isReadOnly"
      @click="$refs.editRoleContext.toggle($event.currentTarget)"
    />
    <EditRoleContext
      ref="editRoleContext"
      :subject="row"
      :roles="roles"
      :workspace="workspace"
      role-value-column="role_uid"
      :show-commercial-info="false"
      @update-role="roleUpdate($event)"
    />
  </div>
</template>

<script>
import RoleSelectorButton from '@baserow/modules/core/components/settings/RoleSelectorButton'

import { clone } from '@baserow/modules/core/utils/object'
import { notifyIf } from '@baserow/modules/core/utils/error'
import EditRoleContext from '@baserow/modules/core/components/settings/members/EditRoleContext'

export default {
  name: 'AgentRoleField',
  components: { EditRoleContext, RoleSelectorButton },
  props: {
    row: { type: Object, required: true },
    column: { type: Object, required: true },
  },
  emits: ['row-update'],
  computed: {
    workspace() {
      return this.column.additionalProps.workspace
    },
    roles() {
      return this.column.additionalProps.roles
    },
    isReadOnly() {
      return !this.$hasPermission('agent.update', this.row, this.workspace.id)
    },
    selectedRole() {
      return this.roles.find((role) => role.uid === this.row.role_uid)
    },
  },
  methods: {
    /** Optimistically updates the role and restores it if the request fails. */
    async roleUpdate({ uid: roleUid, subject: agent }) {
      const oldAgent = clone(agent)
      const newAgent = clone(agent)
      newAgent.role_uid = roleUid
      this.$emit('row-update', newAgent)

      try {
        await this.$store.dispatch('agent/update', {
          agentId: agent.id,
          values: { role_uid: roleUid },
        })
      } catch (error) {
        this.$emit('row-update', oldAgent)
        notifyIf(error, 'agent')
      }
    },
  },
}
</script>
