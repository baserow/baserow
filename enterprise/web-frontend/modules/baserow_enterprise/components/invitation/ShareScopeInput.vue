<template>
  <InviteInput
    ref="input"
    :workspace="workspace"
    :roles="roles"
    :options="options"
    :tabs="tabs"
    :email-role-uids="emailRoleUids"
    :email-disabled-reason="emailDisabledReason"
    :placeholder="placeholder"
    :no-results-text="noResultsText"
    :disabled="disabled"
    @add="(selection, roleUid) => $emit('add', selection, roleUid)"
  >
    <template #submit-label="{ count, role }">
      {{
        count === 0
          ? $t('shareScope.add')
          : $t('shareScope.addAs', { count, role })
      }}
    </template>
    <template #email-description="{ role }">
      {{
        $t('shareScope.inviteEmailDescription', { role, type: scopeTypeName })
      }}
    </template>
    <slot></slot>
  </InviteInput>
</template>

<script>
import InviteInput from '@baserow/modules/core/components/invitation/InviteInput'

/**
 * The input of the share dialog: the common invite input listing the subjects
 * of the workspace next to new email addresses. `subjects` holds the subjects
 * that can be picked per subject type, and every type in it gets a tab. A
 * subject whose key is in `assignedRoles` already holds a role on the object
 * and an address in `pendingEmails` already has an invitation on it, so both
 * are listed with that reason rather than offered. So is a subject in
 * `inheritedAdmins`, who has full access to the object already. Submitting emits `add` with
 * the picked items and the chosen role uid; the parent calls `remove()` and
 * `reset()` once they were added. The default slot is what the dialog shows
 * below the input, including while the suggestions popup is open.
 */
export default {
  name: 'ShareScopeInput',
  components: { InviteInput },
  props: {
    workspace: {
      type: Object,
      required: true,
    },
    scopeTypeName: {
      type: String,
      required: true,
    },
    /**
     * The subjects that can be picked, keyed by subject type, in the order of
     * the tabs.
     */
    subjects: {
      type: Object,
      required: false,
      default: () => ({}),
    },
    /**
     * The role uids of the subjects with a role on the object, as
     * `{ '<subject type>:<id>': '<role uid>' }`.
     */
    assignedRoles: {
      type: Object,
      required: false,
      default: () => ({}),
    },
    pendingEmails: {
      type: Array,
      required: false,
      default: () => [],
    },
    /**
     * The users and agents who are an admin of a level above the object, as
     * `{ '<subject type>:<id>': '<level>' }`. A role on the object would have
     * no effect on them.
     */
    inheritedAdmins: {
      type: Object,
      required: false,
      default: () => ({}),
    },
    roles: {
      type: Array,
      required: true,
    },
    /**
     * The uids of the roles a new address can be invited with, see the roles
     * of the scope invitation target.
     */
    emailRoleUids: {
      type: Array,
      required: false,
      default: null,
    },
    emailDisabledReason: {
      type: String,
      required: false,
      default: null,
    },
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['add'],
  computed: {
    subjectTypes() {
      return Object.keys(this.subjects).map((type) =>
        this.$registry.get('subject', type)
      )
    },
    placeholder() {
      if (this.emailDisabledReason) {
        return this.$t('shareScope.searchSubjectsPlaceholder', {
          subjects: this.formatTabNames('unit'),
        })
      }
      return this.$t('shareScope.searchPlaceholder', {
        subjects: this.formatTabNames('unit'),
      })
    },
    noResultsText() {
      if (this.emailDisabledReason) {
        return this.$t('shareScope.noSubjectResults', {
          subjects: this.formatTabNames('disjunction'),
        })
      }
      return this.$t('shareScope.noResults', {
        subjects: this.formatTabNames('disjunction'),
      })
    },
    tabs() {
      return this.subjectTypes.map((subjectType) => ({
        value: subjectType.type,
        label: subjectType.getTabDisplayName(),
      }))
    },
    options() {
      const subjects = this.subjectTypes.flatMap((subjectType) =>
        this.subjects[subjectType.type].map((subject) =>
          subjectType.getInviteOption(subject)
        )
      )
      const assigned = this.$t('shareScope.alreadyAssigned', {
        type: this.scopeTypeName,
      })
      const pending = this.$t('shareScope.alreadyInvited', {
        type: this.scopeTypeName,
      })
      return [
        ...subjects.map((option) => {
          const roleUid = this.assignedRoles[option.key]
          if (roleUid) {
            return {
              ...option,
              disabledReason: assigned,
              disabledHint: this.$t('shareScope.roleHere', {
                role: this.getRoleName(roleUid),
              }),
            }
          }
          if (this.inheritedAdmins[option.key]) {
            return {
              ...option,
              disabledReason: this.$t('shareScope.alreadyAdmin', {
                type: this.scopeTypeName,
                level: this.inheritedAdmins[option.key],
              }),
              disabledHint: this.$t('shareScope.adminHint'),
            }
          }
          return option
        }),
        ...this.pendingEmails.map((email) => ({
          key: `invitation:${email}`,
          type: 'email',
          email,
          name: email,
          search: email,
          initials: '',
          icon: 'iconoir-mail',
          color: 'neutral',
          disabledReason: pending,
          disabledHint: this.$t('inviteInput.invitedHint'),
        })),
      ]
    },
  },
  methods: {
    getRoleName(roleUid) {
      return (
        this.workspace._.roles.find(({ uid }) => uid === roleUid)?.name ??
        roleUid
      )
    },
    /**
     * The tab names as one list for a sentence, like "members, teams, agents"
     * for the `unit` type or "members, teams, or agents" for `disjunction`.
     */
    formatTabNames(type) {
      const locale = this.$i18n.locale
      return new Intl.ListFormat(locale, { type }).format(
        this.subjectTypes.map((subjectType) =>
          subjectType.getTabDisplayName().toLocaleLowerCase(locale)
        )
      )
    },
    focus() {
      this.$refs.input.focus()
    },
    remove(item) {
      this.$refs.input.remove(item)
    },
    reset() {
      this.$refs.input.reset()
    },
  },
}
</script>
