<template>
  <div
    :title="
      $t('subjectSampleField.titleAttr', {
        subjectCount: row.subject_count,
      })
    "
    :class="{ 'subject-sample-field--clickable': canManageMembers }"
    :role="canManageMembers ? 'button' : null"
    :tabindex="canManageMembers ? 0 : null"
    :aria-label="
      canManageMembers ? $t('subjectSampleField.manageMembers') : null
    "
    @click="manageMembers"
    @keydown.enter.prevent="manageMembers"
    @keydown.space.prevent="manageMembers"
  >
    <div v-if="!row[column.key].length">-</div>

    <component
      :is="getSubjectType(sample.subject_type).avatarComponent"
      v-for="(sample, index) in row[column.key]"
      :key="index"
      class="subject-sample-field-list__avatar"
      size="large"
      :subject="{ name: sample.subject_label }"
    />

    <div
      v-if="row.subject_count > 10"
      class="subject_sample_field-list__user-initials extras"
    >
      +{{ row.subject_count - row[column.key].length }}
    </div>
  </div>
</template>

<script>
/**
 * A sample of the members of a team. When the column allows it with the
 * `canManageMembers` additional prop, clicking it emits `manage-members` with
 * the team, to open its members.
 */
export default {
  name: 'SubjectSampleField',
  emits: ['manage-members'],
  props: {
    row: {
      required: true,
      type: Object,
    },
    column: {
      required: true,
      type: Object,
    },
  },
  computed: {
    canManageMembers() {
      return Boolean(this.column.additionalProps?.canManageMembers)
    },
  },
  methods: {
    manageMembers() {
      if (this.canManageMembers) {
        this.$emit('manage-members', this.row)
      }
    },
    getSubjectType(type) {
      return this.$registry.get('subject', type)
    },
  },
}
</script>
