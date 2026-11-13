<template>
  <div>
    <FormGroup :label="$t('localBaserowForm.subject')" required small-label>
      <PaginatedDropdown
        class="local-baserow-form__subject"
        :value="authenticationSubject"
        :fetch-page="fetchIdentityPage"
        :add-empty-item="false"
        :initial-display-name="initialSubjectName"
        :include-display-name-in-selected-event="true"
        @input="setAuthenticationSubject"
      >
        <template #items="{ results }">
          <DropdownSection :title="userSubjectType.getTabDisplayName()">
            <DropdownItem
              :name="$t('localBaserowForm.currentUser')"
              :value="currentUserKey"
              :icon="userSubjectType.iconClass"
              :description="$t('localBaserowForm.currentUserDescription')"
            />
          </DropdownSection>
          <DropdownSection :title="$t('subjectType.identities')">
            <DropdownItem
              v-for="identity in results"
              :key="identity.id"
              :name="identity.name"
              :value="identity.id"
              :icon="userSubjectType.identityIconClass"
              :description="identity.description"
            />
            <DropdownItem
              v-if="hasIdentities === false"
              :name="$t('localBaserowForm.noIdentities')"
              value="no-identities"
              disabled
            />
          </DropdownSection>
        </template>
      </PaginatedDropdown>
      <template #helper>
        {{ $t('localBaserowForm.subjectMessage') }}
      </template>
    </FormGroup>
  </div>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import PaginatedDropdown from '@baserow/modules/core/components/PaginatedDropdown'
import DropdownSection from '@baserow/modules/core/components/DropdownSection'
import IdentityService from '@baserow/modules/core/services/identity'
import { UserSubjectType } from '@baserow/modules/core/subjectTypes.jsx'

export default {
  components: { PaginatedDropdown, DropdownSection },
  mixins: [form],
  props: {
    application: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      values: {
        authorized_subject_id:
          this.defaultValues.authorized_subject?.id || null,
        authorized_subject_type:
          this.defaultValues.authorized_subject?.type ||
          UserSubjectType.getType(),
      },
      allowedValues: ['authorized_subject_id', 'authorized_subject_type'],
      // Whether the workspace has identities, unknown until they're fetched.
      hasIdentities: null,
    }
  },
  computed: {
    currentUserId() {
      return this.$store.getters['auth/getUserId']
    },
    userSubjectType() {
      return this.$registry.get('subject', UserSubjectType.getType())
    },
    currentUserKey() {
      return this.userSubjectType.getKey({ id: this.currentUserId })
    },
    initialSubjectName() {
      const subject = this.defaultValues.authorized_subject
      // A trashed identity isn't selectable, so show nothing selected and let the
      // user pick another subject.
      if (subject?.trashed) {
        return null
      }
      if (!subject) {
        return this.$t('localBaserowForm.currentUser')
      }
      const subjectType = this.$registry.get('subject', subject.type)
      if (subjectType.isCurrentUser(subject, this.currentUserId)) {
        return this.$t('localBaserowForm.currentUser')
      }
      return subjectType.getDisplayName(subject)
    },
    authenticationSubject() {
      const type = this.values.authorized_subject_type
      const id =
        type === UserSubjectType.getType() &&
        this.values.authorized_subject_id === null
          ? this.currentUserId
          : this.values.authorized_subject_id
      return this.$registry.get('subject', type).getKey({ id })
    },
  },
  methods: {
    /**
     * Fetches a page of the identities of the workspace, with their role as
     * description. The identities endpoint, unlike the subjects one, has it.
     */
    async fetchIdentityPage(page, search) {
      const workspaceId = this.application.workspace.id
      const [response, roles] = await Promise.all([
        IdentityService(this.$client).listPage(workspaceId, { page, search }),
        this.fetchRoles(workspaceId),
      ])
      if (!search) {
        this.hasIdentities = response.data.count > 0
      }
      const results = response.data.results.map((identity) => {
        const role = roles.find(({ uid }) => uid === identity.role_uid)
        return {
          id: this.userSubjectType.getKey(identity),
          subject_id: identity.id,
          name: identity.name,
          description: role
            ? this.$t('localBaserowForm.identityRole', { role: role.name })
            : null,
        }
      })
      return { ...response, data: { ...response.data, results } }
    },
    /**
     * The roles of the workspace, to name the role of each identity. The
     * identities are listed without them if they can't be fetched.
     */
    async fetchRoles(workspaceId) {
      const workspace = this.$store.getters['workspace/get'](workspaceId)
      try {
        await this.$store.dispatch('workspace/fetchRoles', workspace)
      } catch {
        return []
      }
      return workspace._.roles || []
    },
    setAuthenticationSubject({ value, item }) {
      if (value === this.currentUserKey) {
        this.values.authorized_subject_id = this.currentUserId
        this.values.authorized_subject_type = UserSubjectType.getType()
      } else {
        this.values.authorized_subject_id = item.subject_id
        this.values.authorized_subject_type = UserSubjectType.getType()
      }
    },
  },
}
</script>
