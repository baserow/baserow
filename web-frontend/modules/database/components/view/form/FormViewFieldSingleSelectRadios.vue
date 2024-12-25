<template>
  <div>
    <div v-if="field.select_options.length === 0" class="control--messages">
      <p>{{ $t('formViewField.noSelectOptions') }}</p>
    </div>
    <RadioGroup
      :model-value="valueId"
      :options="options"
      vertical-layout
      @input=";[touch(), updateValue($event, value)]"
    >
    </RadioGroup>

    <div v-if="!required" class="margin-top-1">
      <a @click=";[touch(), updateValue(null, value)]">clear value</a>
    </div>
    <div v-show="touched && !valid" class="error">
      {{ error }}
    </div>
  </div>
</template>

<script>
import rowEditField from '@baserow/modules/database/mixins/rowEditField'
import singleSelectField from '@baserow/modules/database/mixins/singleSelectField'

export default {
  name: 'FormViewSingleSelectRadios',
  mixins: [rowEditField, singleSelectField],

  computed: {
    options() {
      return this.field.select_options.map((option) => ({
        label: option.value,
        value: option.id,
      }))
    },
  },
}
</script>
