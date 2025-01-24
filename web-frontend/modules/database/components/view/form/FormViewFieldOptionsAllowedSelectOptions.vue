<template>
  <div>
    <SwitchInput
      class="margin-bottom-1"
      small
      :value="fieldOptions.include_all_select_options"
      :disabled="readOnly"
      @input="
        $emit('updated-field-options', {
          include_all_select_options: $event,
        })
      "
      >{{ $t('formViewField.includeAllSelectOptions') }}</SwitchInput
    >
    <div
      v-if="!fieldOptions.include_all_select_options"
      class="form-view__allowed-select-options"
    >
      <FormGroup
        small-label
        required
        :helper-text="$t('formViewField.includeAllSelectOptionsHelper')"
      >
        <FieldSelectOptionsDropdown
          :value="fieldOptions.allowed_select_options"
          :options="field.select_options"
          :multiple="true"
          :show-empty-value="false"
          @input="
            $emit('updated-field-options', {
              allowed_select_options: $event,
            })
          "
        ></FieldSelectOptionsDropdown>
      </FormGroup>
    </div>
  </div>
</template>

<script>
import FieldSelectOptionsDropdown from '@baserow/modules/database/components/field/FieldSelectOptionsDropdown'

export default {
  name: 'FormViewFieldOptionsAllowedSelectOptions',
  components: { FieldSelectOptionsDropdown },
  props: {
    readOnly: {
      type: Boolean,
      required: true,
    },
    field: {
      type: Object,
      required: true,
    },
    fieldOptions: {
      type: Object,
      required: true,
    },
  },
}
</script>
