<template>
  <div>
    <div v-if="loading" class="loading"></div>
    <template v-else>
      <FormGroup
        small-label
        required
        :label="$t('fieldSingleSelectSubForm.optionsLabel')"
        class="margin-bottom-2"
      >
        <FieldSelectOptions
          ref="selectOptions"
          v-model="values.select_options"
        ></FieldSelectOptions>
      </FormGroup>
      <FormGroup
        small-label
        :label="$t('fieldSingleSelectSubForm.defaultOptionLabel')"
      >
        <Dropdown
          v-model="v$.values.single_select_default.$model"
          :fixed-items="true"
          :disabled="isDefaultValueFieldDisabled"
        >
          <DropdownItem key="empty-option" name="" :value="null" />
          <DropdownItem
            v-for="option in values.select_options"
            :key="option.id"
            :name="option.value"
            :value="option.id"
          />
        </Dropdown>
        <div
          v-if="isDefaultValueFieldDisabled"
          class="control__messages padding-top-0"
        >
          <p
            class="control__helper-text control__helper-text--warning field-context__inner-element-width"
          >
            {{ $t('fieldForm.defaultValueDisabledByConstraint') }}
          </p>
        </div>
      </FormGroup>
    </template>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import fieldOptionsSubForm from '@baserow/modules/database/mixins/fieldOptionsSubForm'

export default {
  name: 'FieldSingleSelectOptionsSubForm',
  mixins: [fieldOptionsSubForm],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      allowedValues: ['select_options', 'single_select_default'],
      values: {
        single_select_default: null,
      },
    }
  },
  validations() {
    return {
      values: {
        single_select_default: {},
      },
    }
  },
  watch: {
    'values.select_options': {
      handler(newOptions) {
        const optionIds = newOptions.map((option) => option.id)
        if (
          this.values.single_select_default &&
          !optionIds.includes(this.values.single_select_default)
        ) {
          this.values.single_select_default = null
        }
      },
      deep: true,
    },
  },
}
</script>
