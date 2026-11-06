<template>
  <Modal ref="modal">
    <h2 class="margin-bottom-1">{{ $t('createTeamModal.title') }}</h2>
    <p>{{ $t('manageTeamModals.subheading') }}</p>
    <Error :error="error"></Error>
    <ManageTeamForm
      ref="manageForm"
      :workspace="workspace"
      :loading="loading"
      @submitted="createTeam"
    >
    </ManageTeamForm>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'
import ManageTeamForm from '@baserow_enterprise/components/teams/ManageTeamForm'
import TeamService from '@baserow_enterprise/services/team'

/**
 * Creates a team with a name and a role. Members are added afterwards in the
 * invite modal of the team.
 */
export default {
  name: 'CreateTeamModal',
  emits: ['created'],
  components: { ManageTeamForm },
  mixins: [modal, error],
  props: {
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
  methods: {
    show(...args) {
      this.hideError()
      modal.methods.show.bind(this)(...args)
    },
    async createTeam(values) {
      this.loading = true

      try {
        const { data } = await TeamService(this.$client).create(
          this.workspace.id,
          { name: values.name, default_role: values.default_role }
        )
        this.loading = false
        this.$refs.manageForm.reset()
        this.$emit('created', data)
        this.hide()
      } catch (error) {
        this.loading = false
        this.handleError(error, 'team', {
          ERROR_TEAM_NAME_NOT_UNIQUE: new ResponseErrorMessage(
            this.$t('createTeamModal.invalidNameTitle'),
            this.$t('createTeamModal.invalidNameMessage')
          ),
        })
      }
    },
  },
}
</script>
