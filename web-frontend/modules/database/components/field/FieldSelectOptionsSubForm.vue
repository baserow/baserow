<template>
  <div>
    <div v-if="loading" class="loading"></div>
    <FormGroup
      v-else
      small-label
      required
      :label="$t('fieldSingleSelectSubForm.optionsLabel')"
    >
      <FieldSelectOptions
        ref="selectOptions"
        v-model="values.select_options"
      ></FieldSelectOptions>
    </FormGroup>
  </div>
</template>

<script>
import fieldOptionsSubForm from '@baserow/modules/database/mixins/fieldOptionsSubForm'

export default {
  name: 'FieldSelectOptionsSubForm',
  mixins: [fieldOptionsSubForm],
}
</script>
