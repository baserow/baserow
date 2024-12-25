<template>
  <div class="control__elements">
    <FieldSelectOptionsDropdown
      :value="valueId"
      :options="singleSelectOptions"
      :allow-create-option="allowCreateOptions"
      :disabled="readOnly"
      :error="touched && !valid"
      size="large"
      @input="updateValue($event, value)"
      @create-option="createOption($event)"
      @hide="touch()"
    ></FieldSelectOptionsDropdown>
    <div v-show="touched && !valid" class="error">
      {{ error }}
    </div>
  </div>
</template>

<script>
import rowEditField from '@baserow/modules/database/mixins/rowEditField'
import singleSelectField from '@baserow/modules/database/mixins/singleSelectField'
import FieldSelectOptionsDropdown from '@baserow/modules/database/components/field/FieldSelectOptionsDropdown'

export default {
  name: 'RowEditFieldSingleSelect',
  components: { FieldSelectOptionsDropdown },
  mixins: [rowEditField, singleSelectField],
  props: {
    allowCreateOptions: {
      type: Boolean,
      default: true,
      required: false,
    },
  },
  computed: {
    singleSelectOptions() {
      if (this.field.select_options) {
        return this.field.select_options
      } else if (this.value) {
        return [this.value]
      } else {
        return []
      }
    },
  },
}
</script>
