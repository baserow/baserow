<template>
  <Modal ref="modal">
    <h2 class="margin-bottom-1">{{ $t('createTeamModal.title') }}</h2>
    <p>{{ $t('manageTeamModals.subheading') }}</p>
    <Error :error="error"></Error>
    <ManageTeamForm
      ref="manageForm"
      :workspace="workspace"
      :loading="loading"
      :invited-subjects="invitedSubjects"
      @submitted="createTeam"
      @remove-subject="removeSubject"
      @invite="showSubjectAssignmentModal"
    >
    </ManageTeamForm>
    <MemberAssignmentModal
      ref="memberAssignmentModal"
      :members="uninvitedSubjects"
      :title="$t('manageTeamForm.accessModalTitle')"
      :description="$t('manageTeamForm.accessModalDescription')"
      @select="storeSelectedSubjects"
    />
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'
import ManageTeamForm from '@baserow_enterprise/components/teams/ManageTeamForm'
import TeamService from '@baserow_enterprise/services/team'
import MemberAssignmentModal from '@baserow/modules/core/components/workspace/MemberAssignmentModal'
import AgentService from '@baserow/modules/core/services/agent'
import { FF_AGENTS } from '@baserow/modules/core/plugins/featureFlags'
import {
  getTeamSubjectKey,
  makeTeamSubject,
} from '@baserow_enterprise/utils/teamSubjects'

export default {
  name: 'CreateTeamModal',
  emits: ['created'],
  components: { ManageTeamForm, MemberAssignmentModal },
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
      invitedSubjects: [],
      agents: [],
    }
  },
  computed: {
    canListAgents() {
      return (
        this.$featureFlagIsEnabled(FF_AGENTS) &&
        this.$hasPermission(
          'workspace.list_agents',
          this.workspace,
          this.workspace.id
        )
      )
    },
    availableSubjects() {
      const userSubjectType = this.$registry.get('subject', 'auth.User')
      const agentSubjectType = this.$registry.get('subject', 'core.Agent')
      return [
        ...this.workspace.users.map((member) =>
          makeTeamSubject(member, userSubjectType)
        ),
        ...this.agents.map((agent) =>
          makeTeamSubject(
            agent,
            agentSubjectType,
            this.$t('manageTeamForm.agentLabel')
          )
        ),
      ]
    },
    uninvitedSubjects() {
      const invitedSubjectKeys = this.invitedSubjects.map(getTeamSubjectKey)
      return this.availableSubjects.filter(
        (subject) => !invitedSubjectKeys.includes(getTeamSubjectKey(subject))
      )
    },
  },
  methods: {
    show(...args) {
      this.hideError()
      // Reset the array of invited subjects.
      this.invitedSubjects = []
      modal.methods.show.bind(this)(...args)
    },
    removeSubject(removal) {
      // Remove them as an invited subject.
      const removalKey = getTeamSubjectKey(removal)
      this.invitedSubjects = this.invitedSubjects.filter(
        (subject) => getTeamSubjectKey(subject) !== removalKey
      )
    },
    storeSelectedSubjects(selections) {
      this.invitedSubjects = this.invitedSubjects.concat(selections)
    },
    async showSubjectAssignmentModal() {
      this.agents = []
      try {
        if (this.canListAgents) {
          const { data } = await AgentService(this.$client).list(
            this.workspace.id
          )
          this.agents = data.results || data
        }
      } catch (error) {
        this.handleError(error, 'team')
      } finally {
        this.$refs.memberAssignmentModal.show()
      }
    },
    async createTeam(values) {
      this.loading = true

      try {
        const { data } = await TeamService(this.$client).create(
          this.workspace.id,
          values
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
