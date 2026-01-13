<template>
  <div>
    <slot
      v-if="canCreateSingleSelectField || singleSelectFields.length > 0"
    ></slot>
    <div v-else class="warning">
      {{ $t('chooseSingleSelectField.warningWhenNothingToChooseOrCreate') }}
    </div>

    <RadioGroup
      :model-value="value"
      vertical-layout
      :options="singleSelectFieldsOptions"
      :disabled="loading || readOnly"
      @input="$emit('input', $event)"
    >
    </RadioGroup>

    <div v-if="canCreateSingleSelectField" class="margin-top-2">
      <span ref="createFieldContextLink">
        <ButtonText
          icon="iconoir-plus"
          class="choose-select-field__link margin-right-auto"
          @click="$refs.createFieldContext.toggle($refs.createFieldContextLink)"
        >
          {{ $t('chooseSingleSelectField.addSelectField') }}
        </ButtonText></span
      >

      <CreateFieldContext
        ref="createFieldContext"
        :table="table"
        :view="view"
        :forced-type="singleSelectFieldType"
        :all-fields-in-table="fields"
        :database="database"
        @field-created="$event.callback()"
      ></CreateFieldContext>
    </div>
  </div>
</template>

<script>
import { SingleSelectFieldType } from '@baserow/modules/database/fieldTypes'
import CreateFieldContext from '@baserow/modules/database/components/field/CreateFieldContext'

export default {
  name: 'ChooseSingleSelectField',
  components: { CreateFieldContext },
  props: {
    table: {
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
    fields: {
      type: Array,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: false,
      default: false,
    },
    value: {
      required: true,
      validator() {
        return true
      },
    },
    loading: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['input'],

  computed: {
    canCreateSingleSelectField() {
      return (
        !this.readOnly &&
        this.$hasPermission(
          'database.table.create_field',
          this.table,
          this.database.workspace.id
        )
      )
    },
    singleSelectFieldType() {
      return SingleSelectFieldType.getType()
    },
    singleSelectFields() {
      return this.fields.filter(
        (field) => field.type === this.singleSelectFieldType
      )
    },
    singleSelectFieldsOptions() {
      return this.singleSelectFields.map((singleSelectField) => {
        return {
          label: singleSelectField.name,
          value: singleSelectField.id,
        }
      })
    },
  },
  watch: {
    loading(isLoading) {
      if (isLoading)
        this.singleSelectFieldsOptions.find(
          (option) => option.value === this.value
        ).loading = true
    },
  },
}
</script>
