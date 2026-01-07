<template>
  <Modal ref="modal">
    <h2 class="margin-bottom-1">{{ $t('createTeamModal.title') }}</h2>
    <p>{{ $t('manageTeamModals.subheading') }}</p>
    <Error :error="error"></Error>
    <ManageTeamForm
      ref="manageForm"
      :workspace="workspace"
      :loading="loading"
      :invited-user-subjects="invitedUserSubjects"
      @submitted="createTeam"
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
      // Reset the array of invited subjects.
      this.invitedUserSubjects = []
      modal.methods.show.bind(this)(...args)
    },
    removeSubject(removal) {
      // Remove them as an invited subject.
      this.invitedUserSubjects = this.invitedUserSubjects.filter(
        (subj) => subj.user_id !== removal.user_id
      )
    },
    storeSelectedUsers(selections) {
      this.invitedUserSubjects = this.invitedUserSubjects.concat(selections)
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
