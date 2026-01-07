<template>
  <div class="margin-top-3">
    <ChooseSingleSelectField
      :view="view"
      :table="table"
      :fields="selectFields"
      :database="database"
      :value="value"
      @input="$emit('update', { field_id: $event })"
    >
      <div class="margin-bottom-2">
        {{ $t('singleSelectColorValueProviderForm.chooseAColor') }}
      </div>
    </ChooseSingleSelectField>
  </div>
</template>

<script>
import ChooseSingleSelectField from '@baserow/modules/database/components/field/ChooseSingleSelectField.vue'
import { SingleSelectFieldType } from '@baserow/modules/database/fieldTypes'

export default {
  name: 'SingleSelectColorValueProviderForm',
  emits: ['update'],
  components: { ChooseSingleSelectField },
  props: {
    options: {
      type: Object,
      required: true,
    },
    database: {
      type: Object,
      required: true,
    },
    view: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
  },
  computed: {
    selectFields() {
      return this.fields.filter(
        ({ type }) => type === SingleSelectFieldType.getType()
      )
    },
    value() {
      return this.options && this.options.field_id
    },
  },
}
</script>
