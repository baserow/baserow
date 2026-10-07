<template>
  <div>
    <FormGroup :label="$t('localBaserowForm.subject')" required small-label>
      <Dropdown v-model="authenticationSubject" :disabled="loadingSubjects">
        <DropdownItem
          :name="$t('localBaserowForm.currentUser')"
          value="user"
          icon="iconoir-user"
        />
        <DropdownItem
          v-for="subject in subjects"
          :key="subject.id"
          :name="subject.name"
          :value="subject.id"
          icon="baserow-icon-agent"
        />
      </Dropdown>
      <template #helper>
        {{ $t('localBaserowForm.subjectMessage') }}
      </template>
    </FormGroup>
  </div>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import SubjectService from '@baserow/modules/core/services/subject'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
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
      subjects: [],
      loadingSubjects: false,
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
        } else {
          const subject = this.subjects.find((subject) => subject.id === value)
          this.values.authorized_subject_id = subject.subject_id
          this.values.authorized_subject_type = subject.subject_type
        }
      },
    },
  },
  async mounted() {
    this.loadingSubjects = true
    try {
      const { data } = await SubjectService(this.$client).list(
        this.application.workspace.id
      )
      this.subjects = data.results.filter(
        (subject) => subject.subject_type === 'core.Agent'
      )
    } catch (error) {
      notifyIf(error, 'subject')
    } finally {
      this.loadingSubjects = false
    }
  },
}
</script>
