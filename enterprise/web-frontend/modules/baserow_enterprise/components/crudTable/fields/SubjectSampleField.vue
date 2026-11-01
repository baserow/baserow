<template>
  <div
    :title="
      $t('subjectSampleField.titleAttr', {
        subjectCount: row.subject_count,
      })
    "
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
export default {
  name: 'SubjectSampleField',
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
  methods: {
    getSubjectType(type) {
      return this.$registry.get('subject', type)
    },
  },
}
</script>
