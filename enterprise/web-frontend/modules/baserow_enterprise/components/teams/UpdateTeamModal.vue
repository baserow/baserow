<template>
  <Modal ref="modal">
    <h2 class="margin-bottom-1">
      {{ $t('updateTeamModal.title', { teamName: team.name }) }}
    </h2>
    <p>{{ $t('manageTeamModals.subheading') }}</p>
    <Error :error="error"></Error>
    <ManageTeamForm
      ref="manageForm"
      :workspace="workspace"
      :loading="loading"
      :default-values="team"
      @submitted="updateTeam"
    >
      <TeamMembersSummary
        :team="team"
        :can-manage-members="canListMembers"
        @manage="manageMembers"
      />
    </ManageTeamForm>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'
import ManageTeamForm from '@baserow_enterprise/components/teams/ManageTeamForm'
import TeamMembersSummary from '@baserow_enterprise/components/teams/TeamMembersSummary'
import TeamService from '@baserow_enterprise/services/team'

/**
 * Changes the name and the role of a team. Its members are managed in the
 * invite modal of the team, so they are left as they are. The members are
 * summarised under the form, and its button closes this modal and emits
 * `manage-members` with the team, so that the invite modal can be opened
 * instead.
 */
export default {
  name: 'UpdateTeamModal',
  emits: ['updated', 'manage-members'],
  components: { ManageTeamForm, TeamMembersSummary },
  mixins: [modal, error],
  props: {
    team: {
      type: Object,
      required: false,
      default: () => ({}),
    },
    workspace: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      loading: false,
    }
  },
  computed: {
    canListMembers() {
      return this.$hasPermission(
        'enterprise.teams.list_subjects',
        this.workspace,
        this.workspace.id
      )
    },
  },
  methods: {
    manageMembers() {
      this.hide()
      this.$emit('manage-members', this.team)
    },
    show(...args) {
      this.hideError()
      modal.methods.show.bind(this)(...args)
    },
    async updateTeam(values) {
      this.loading = true

      try {
        const { data } = await TeamService(this.$client).update(this.team.id, {
          name: values.name,
          default_role: values.default_role,
        })
        this.loading = false
        this.$refs.manageForm.reset()
        this.$emit('updated', data)
        this.hide()
      } catch (error) {
        this.loading = false
        this.handleError(error, 'team', {
          ERROR_TEAM_NAME_NOT_UNIQUE: new ResponseErrorMessage(
            this.$t('updateTeamModal.invalidNameTitle'),
            this.$t('updateTeamModal.invalidNameMessage')
          ),
        })
      }
    },
  },
}
</script>
