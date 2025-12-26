<template>
  <div
    :title="
      $t('subjectSampleField.titleAttr', {
        subjectCount: row.subject_count,
      })
    "
  >
    <div v-if="!row[column.key].length">-</div>

    <Avatar
      v-for="(sample, index) in row[column.key]"
      :key="index"
      class="subject-sample-field-list__avatar"
      rounded
      size="large"
      :initials="nameAbbreviation(sample.subject_label)"
    ></Avatar>

    <div
      v-if="row.subject_count > 10"
      class="subject_sample_field-list__user-initials extras"
    >
      +{{ row.subject_count - row[column.key].length }}
    </div>
  </div>
</template>

<script>
import nameAbbreviation from '@baserow/modules/core/filters/nameAbbreviation'

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
    nameAbbreviation,
  },
}
</script>
