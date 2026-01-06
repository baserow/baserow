<template>
  <div>
    <FieldSelectThroughFieldSubForm
      :fields="allFieldsInTable"
      :database="database"
      :default-values="defaultValues"
    ></FieldSelectThroughFieldSubForm>
  </div>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import fieldSubForm from '@baserow/modules/database/mixins/fieldSubForm'
import FieldSelectThroughFieldSubForm from '@baserow/modules/database/components/field/FieldSelectThroughFieldSubForm'

export default {
  name: 'FieldCountSubForm',
  components: { FieldSelectThroughFieldSubForm },
  mixins: [form, fieldSubForm],
  data() {
    return {
      allowedValues: [],
      values: {},
    }
  },
}
</script>
