<template>
  <div
    :class="[data.staticClass, data.class]"
    :title="
      parent.$t('subjectSampleField.titleAttr', {
        subjectCount: props.row.subject_count,
      })
    "
    v-on="listeners"
  >
    <div v-if="!props.row[props.column.key].length">-</div>

    <Avatar
      v-for="(sample, index) in props.row[props.column.key]"
      :key="index"
      class="subject-sample-field-list__avatar"
      rounded
      size="large"
      :initials="sample.subject_label | nameAbbreviation"
    ></Avatar>

    <div
      v-if="props.row.subject_count > 10"
      class="subject_sample_field-list__user-initials extras"
    >
      +{{ props.row.subject_count - props.row[props.column.key].length }}
    </div>
  </div>
</template>

<script>
export default {
  name: 'SubjectSampleField',
  functional: true,
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
}
</script>
