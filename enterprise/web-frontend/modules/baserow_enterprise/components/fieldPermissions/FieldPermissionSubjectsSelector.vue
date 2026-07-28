<template>
  <div class="field-permission-subjects margin-top-2">
    <Alert type="info-neutral" class="margin-bottom-2">
      <p>{{ $t('fieldPermissionSubjectsSelector.accessNote') }}</p>
    </Alert>

    <section class="field-permission-subjects__section">
      <h3>{{ $t('fieldPermissionSubjectsSelector.addPeopleOrTeams') }}</h3>
      <PaginatedDropdown
        ref="subjectDropdown"
        :value="null"
        :fetch-page="fetchSubjectOptions"
        :value-name="getOptionDisplayName"
        :result-item-component="fieldPermissionSubjectDropdownItem"
        id-name="key"
        size="large"
        :fixed-items="true"
        :fetch-on-open="true"
        :add-empty-item="false"
        :include-display-name-in-selected-event="true"
        :not-selected-text="
          $t('fieldPermissionSubjectsSelector.searchPlaceholder')
        "
        :search-text="$t('fieldPermissionSubjectsSelector.searchHint')"
        @input="addSubjectFromDropdown"
      />
    </section>

    <section class="field-permission-subjects__section margin-top-3">
      <div class="field-permission-subjects__section-heading">
        <h3>{{ $t('fieldPermissionSubjectsSelector.canEdit') }}</h3>
        <span class="field-permission-subjects__count">
          {{ selectedSubjects.length }}
        </span>
      </div>

      <div
        v-if="selectedSubjects.length === 0"
        class="field-permission-subjects__empty"
      >
        {{ $t('fieldPermissionSubjectsSelector.noSelectedSubjects') }}
      </div>
      <ul v-else class="field-permission-subjects__list">
        <li
          v-for="subject in selectedSubjects"
          :key="subject.key"
          class="field-permission-subjects__item"
        >
          <div class="field-permission-subjects__identity">
            <Avatar
              v-if="subject.subjectType === userSubjectType"
              rounded
              size="large"
              :initials="nameAbbreviation(subject.label)"
            ></Avatar>
            <span v-else class="field-permission-subjects__team-icon">
              <i class="iconoir-group"></i>
            </span>
            <span class="field-permission-subjects__details">
              <span class="field-permission-subjects__label">
                {{ subject.label }}
              </span>
              <small v-if="subject.description">{{
                subject.description
              }}</small>
            </span>
          </div>
          <ButtonIcon
            size="small"
            icon="iconoir-cancel"
            :aria-label="
              $t('fieldPermissionSubjectsSelector.remove', {
                subject: subject.label,
              })
            "
            @click="removeSubject(subject)"
          />
        </li>
      </ul>
    </section>
  </div>
</template>

<script>
import { markRaw } from 'vue'

import nameAbbreviation from '@baserow/modules/core/filters/nameAbbreviation'
import PaginatedDropdown from '@baserow/modules/core/components/PaginatedDropdown'
import FieldPermissionSubjectDropdownItem from '@baserow_enterprise/components/fieldPermissions/FieldPermissionSubjectDropdownItem'
import FieldPermissionService from '@baserow_enterprise/services/fieldPermissions'

const USER_SUBJECT_TYPE = 'auth.User'
const TEAM_SUBJECT_TYPE = 'baserow_enterprise.Team'

export default {
  name: 'FieldPermissionSubjectsSelector',
  components: { PaginatedDropdown },
  props: {
    fieldId: {
      type: Number,
      required: true,
    },
    subjects: {
      type: Array,
      default: () => [],
    },
  },
  emits: ['selection-change'],
  data() {
    return {
      pageSize: 20,
      selectedSubjects: [],
      userSubjectType: USER_SUBJECT_TYPE,
      fieldPermissionSubjectDropdownItem: markRaw(
        FieldPermissionSubjectDropdownItem
      ),
    }
  },
  computed: {
    selectedKeys() {
      return new Set(this.selectedSubjects.map(({ key }) => key))
    },
    selectedUserIds() {
      return this.selectedSubjects
        .filter(({ subjectType }) => subjectType === USER_SUBJECT_TYPE)
        .map(({ subjectId }) => subjectId)
    },
    selectedTeamIds() {
      return this.selectedSubjects
        .filter(({ subjectType }) => subjectType === TEAM_SUBJECT_TYPE)
        .map(({ subjectId }) => subjectId)
    },
  },
  watch: {
    subjects: {
      handler() {
        this.reset()
      },
      deep: true,
      immediate: true,
    },
  },
  methods: {
    reset() {
      this.selectedSubjects = this.subjects.map(this.normalizeAssignment)
      this.emitSelectionChange()
      this.resetSubjectDropdown()
    },
    resetSubjectDropdown() {
      this.$nextTick(() => this.$refs.subjectDropdown?.reset())
    },
    subjectKey(subjectType, subjectId) {
      return `${subjectType}:${subjectId}`
    },
    normalizeAssignment(assignment) {
      const subject = assignment.subject
      const isUser = assignment.subject_type === USER_SUBJECT_TYPE
      const label = isUser
        ? subject.first_name || subject.username || subject.email
        : subject.name
      return {
        key: this.subjectKey(assignment.subject_type, assignment.subject_id),
        subjectId: assignment.subject_id,
        subjectType: assignment.subject_type,
        label,
        description: isUser
          ? null
          : this.$t('fieldPermissionSubjectsSelector.teamDescription'),
      }
    },
    normalizeOption(option) {
      const isUser = option.subject_type === USER_SUBJECT_TYPE
      return {
        key: this.subjectKey(option.subject_type, option.subject_id),
        subjectId: option.subject_id,
        subjectType: option.subject_type,
        label: option.name,
        searchText: option.email || '',
        description: isUser
          ? null
          : this.$t('fieldPermissionSubjectsSelector.teamSearchDescription', {
              count: option.subject_count,
            }),
      }
    },
    getOptionDisplayName(subject) {
      return [subject.label, subject.searchText].filter(Boolean).join(' ')
    },
    async fetchSubjectOptions(page, search) {
      const normalizedSearch = (search || '').trim()
      const response = await FieldPermissionService(
        this.$client
      ).fetchSubjectOptions(this.fieldId, {
        page,
        size: this.pageSize,
        search: normalizedSearch,
        exclude_user_ids: this.selectedUserIds.join(','),
        exclude_team_ids: this.selectedTeamIds.join(','),
      })
      return {
        ...response,
        data: {
          ...response.data,
          results: response.data.results.map(this.normalizeOption),
        },
      }
    },
    addSubjectFromDropdown(selection) {
      if (selection?.item) {
        this.addSubject(selection.item)
      }
      this.resetSubjectDropdown()
    },
    addSubject(subject) {
      if (!this.selectedKeys.has(subject.key)) {
        this.selectedSubjects.push(subject)
        this.emitSelectionChange()
      }
    },
    removeSubject(subject) {
      this.selectedSubjects = this.selectedSubjects.filter(
        ({ key }) => key !== subject.key
      )
      this.emitSelectionChange()
      this.resetSubjectDropdown()
    },
    emitSelectionChange() {
      this.$emit('selection-change', this.selectedSubjects.length)
    },
    getSelectedSubjects() {
      return this.selectedSubjects.map(({ subjectId, subjectType }) => ({
        subject_id: subjectId,
        subject_type: subjectType,
      }))
    },
    nameAbbreviation,
  },
}
</script>
