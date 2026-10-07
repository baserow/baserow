<template>
  <div>
    <FormGroup :label="$t('localBaserowForm.subject')" required small-label>
      <PaginatedDropdown
        :value="authenticationSubject"
        :fetch-page="fetchAgentPage"
        :add-empty-item="false"
        :initial-display-name="defaultValues.authorized_subject?.name || null"
        :include-display-name-in-selected-event="true"
        @input="setAuthenticationSubject"
      >
        <template #items="{ results }">
          <DropdownItem
            :name="$t('localBaserowForm.currentUser')"
            value="user"
            icon="iconoir-user"
          />
          <DropdownItem
            v-for="subject in results"
            :key="subject.id"
            :name="subject.name"
            :value="subject.id"
            icon="baserow-icon-agent"
          />
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
import SubjectService from '@baserow/modules/core/services/subject'

export default {
  components: { PaginatedDropdown },
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
          this.defaultValues.authorized_subject?.type || 'auth.User',
      },
      allowedValues: ['authorized_subject_id', 'authorized_subject_type'],
    }
  },
  computed: {
    currentUserId() {
      return this.$store.getters['auth/getUserId']
    },
    authenticationSubject: {
      get() {
        return this.values.authorized_subject_type === 'auth.User' &&
          !this.defaultValues.authorized_subject
          ? 'user'
          : `${this.values.authorized_subject_type}:${this.values.authorized_subject_id}`
      },
      set(value) {
        if (value === 'user') {
          this.values.authorized_subject_id = this.currentUserId
          this.values.authorized_subject_type = 'auth.User'
        }
      },
    },
  },
  methods: {
    fetchAgentPage(page, search) {
      return SubjectService(this.$client).list(this.application.workspace.id, {
        page,
        search,
        subjectTypes: 'core.Agent',
      })
    },
    setAuthenticationSubject({ value, item }) {
      if (value === 'user') {
        this.authenticationSubject = value
      } else {
        this.values.authorized_subject_id = item.subject_id
        this.values.authorized_subject_type = item.subject_type
      }
    },
  },
}
</script>
