<template>
  <div>
    <span v-if="isReadOnly">{{ roleName }}</span>
    <a
      v-else
      ref="editRoleContextLink"
      class="member-role-field__link"
      @click.prevent="$refs.editRoleContext.toggle($refs.editRoleContextLink)"
    >
      <span>{{ roleName }}</span>
      <i class="iconoir-nav-arrow-down"></i>
    </a>
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
import { clone } from '@baserow/modules/core/utils/object'
import { notifyIf } from '@baserow/modules/core/utils/error'
import EditRoleContext from '@baserow/modules/core/components/settings/members/EditRoleContext'

export default {
  name: 'AgentRoleField',
  components: { EditRoleContext },
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
    roleName() {
      return (
        this.roles.find((role) => role.uid === this.row.role_uid)?.name ||
        this.row.role_uid
      )
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
