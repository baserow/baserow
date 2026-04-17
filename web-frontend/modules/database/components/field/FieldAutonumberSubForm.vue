<template>
  <div>
    <p
      v-if="showDuplicateWarning"
      class="control__helper-text control__helper-text--warning field-context__inner-element-width"
    >
      {{ $t('fieldAutonumberSubForm.duplicateWarning') }}
    </p>
  </div>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import fieldSubForm from '@baserow/modules/database/mixins/fieldSubForm'

export default {
  name: 'FieldAutonumberSubForm',
  mixins: [form, fieldSubForm],
  data() {
    return {
      allowedValues: ['view_id'],
      values: { view_id: null },
    }
  },
  computed: {
    showDuplicateWarning() {
      return (
        this.defaultValues.id &&
        this.defaultValues.is_unique_constraint_applied === false
      )
    },
  },
  methods: {
    getDefaultValues() {
      return {
        view_id: this.view.id,
      }
    },
  },
}
</script>
