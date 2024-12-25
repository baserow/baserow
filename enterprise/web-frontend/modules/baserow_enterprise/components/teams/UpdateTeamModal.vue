<template>
  <Modal>
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
      :subjects-loading="subjectsLoading"
      :invited-user-subjects="invitedUserSubjects"
      @submitted="updateTeam"
      @remove-subject="removeSubject"
      @invite="$refs.memberAssignmentModal.show()"
    >
    </ManageTeamForm>
    <MemberAssignmentModal
      ref="memberAssignmentModal"
      :members="uninvitedUserSubjects"
      @invite="storeSelectedUsers"
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

export {}

export default {
  name: 'UpdateTeamModal',
  components: { ManageTeamForm, MemberAssignmentModal },
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
      subjectsLoading: false,
      invitedUserSubjects: [],
    }
  },
  computed: {
    uninvitedUserSubjects() {
      // Pluck out the user IDs in the objects of the `selections` array.
      const invitedSubjectIds = this.invitedUserSubjects.map((subj) => subj.id)
      // Return an array of workspace users who aren't already invited.
      return this.workspace.users.filter(
        (user) => !invitedSubjectIds.includes(user.id)
      )
    },
  },
  methods: {
    show(...args) {
      this.hideError()
      this.parseSubjectsAndMembers()
      modal.methods.show.bind(this)(...args)
    },
    removeSubject(removal) {
      // Remove them as an invited subject.
      this.invitedUserSubjects = this.invitedUserSubjects.filter(
        (subj) => subj.user_id !== removal.user_id
      )
    },
    async parseSubjectsAndMembers() {
      this.subjectsLoading = true
      // Fetch the subjects in this team, and the users in the workspace in parallel.
      const { data } = await TeamService(this.$client).fetchAllSubjects(
        this.team.id
      )
      this.teamSubjects = data
      this.subjectsLoading = false

      // Extract the subjects which are Users.
      const userSubjects = this.teamSubjects.filter(
        (subject) => subject.subject_type === 'auth.User'
      )
      // Extract the user subject PKs.
      const userIds = userSubjects.map((subject) => subject.subject_id)

      // Using those user PKs, find the members records in `this.workspace.user`.
      const invitedMembers = this.workspace.users.filter((member) =>
        userIds.includes(member.user_id)
      )
      // Assign `invitedUserSubjects` our list of WorkspaceUser records who are NOT subjects in this team.
      this.invitedUserSubjects = invitedMembers
    },
    storeSelectedUsers(selections) {
      // Merge the new members into `invitedUserSubjects`.
      this.invitedUserSubjects = this.invitedUserSubjects.concat(selections)
    },
    async updateTeam(values) {
      this.loading = true

      try {
        const { data } = await TeamService(this.$client).update(this.team.id, {
          name: values.name,
          subjects: values.subjects,
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
