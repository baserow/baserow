<template>
  <div>
    <div v-if="loading" class="loading"></div>
    <template v-else>
      <FormGroup
        small-label
        required
        :label="$t('fieldMultipleSelectSubForm.optionsLabel')"
        class="margin-bottom-2"
      >
        <FieldSelectOptions
          ref="selectOptions"
          v-model="values.select_options"
        ></FieldSelectOptions>
      </FormGroup>
      <FormGroup
        small-label
        :label="$t('fieldMultipleSelectSubForm.defaultOptionsLabel')"
      >
        <Dropdown
          v-model="v$.values.multiple_select_default.$model"
          :fixed-items="true"
          :multiple="true"
          :disabled="defaultValueDisabled"
        >
          <DropdownItem
            v-for="option in values.select_options"
            :key="option.id"
            :name="option.value"
            :value="option.id"
          />
        </Dropdown>
      </FormGroup>
    </template>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import fieldOptionsSubForm from '@baserow/modules/database/mixins/fieldOptionsSubForm'

export default {
  name: 'FieldMultipleSelectOptionsSubForm',
  mixins: [fieldOptionsSubForm],
  props: {
    defaultValueDisabled: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      allowedValues: ['select_options', 'multiple_select_default'],
      values: {
        multiple_select_default: [],
      },
    }
  },
  validations() {
    return {
      values: {
        multiple_select_default: {},
      },
    }
  },

  watch: {
    'values.select_options': {
      handler(newOptions) {
        const optionIds = newOptions.map((option) => option.id)
        if (
          this.values.multiple_select_default &&
          Array.isArray(this.values.multiple_select_default) &&
          this.values.multiple_select_default.some(
            (id) => !optionIds.includes(id)
          )
        ) {
          this.values.multiple_select_default =
            this.values.multiple_select_default.filter((id) =>
              optionIds.includes(id)
            )
        }
      },
      deep: true,
    },
    'values.multiple_select_default': {
      handler(newVal) {
        if (newVal === null) {
          this.values.multiple_select_default = []
        }
      },
      immediate: true,
    },
  },
}
</script>
