<template>
  <Context ref="context" overflow-scroll max-height-if-outside-viewport>
    <template v-if="Object.keys(team).length > 0">
      <ul class="context__menu">
        <li
          v-if="
            $hasPermission(
              'enterprise.teams.team.update',
              workspace,
              workspace.id
            )
          "
          class="context__menu-item"
        >
          <a class="context__menu-item-link" @click="handleEditClick(team)">
            <i class="context__menu-item-icon iconoir-edit-pencil"></i>
            {{ $t('editTeamContext.edit') }}
          </a>
        </li>
        <li
          v-if="
            $hasPermission(
              'enterprise.teams.team.delete',
              workspace,
              workspace.id
            )
          "
          class="context__menu-item context__menu-item--with-separator"
        >
          <a
            :class="{
              'context__menu-item-link--loading': removeLoading,
            }"
            class="context__menu-item-link context__menu-item-link--delete"
            @click.prevent="remove(team)"
          >
            <i class="context__menu-item-icon iconoir-bin"></i>
            {{ $t('editTeamContext.remove') }}
          </a>
        </li>
      </ul>
    </template>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'
import { notifyIf } from '@baserow/modules/core/utils/error'
import TeamService from '@baserow_enterprise/services/team'

export default {
  name: 'EditTeamContext',
  emits: ['deleted', 'edit'],
  mixins: [context],
  props: {
    workspace: {
      required: true,
      type: Object,
    },
    team: {
      required: true,
      type: Object,
    },
  },
  data() {
    return {
      removeLoading: false,
    }
  },
  methods: {
    handleEditClick(team) {
      this.$emit('edit', team)
      this.hide()
    },
    async remove(team) {
      if (this.removeLoading) {
        return
      }

      this.removeLoading = true

      try {
        await TeamService(this.$client).delete(team.id)
        this.$emit('deleted', team.id)
        this.hide()
      } catch (error) {
        notifyIf(error)
      } finally {
        this.removeLoading = false
      }
    },
  },
}
</script>
