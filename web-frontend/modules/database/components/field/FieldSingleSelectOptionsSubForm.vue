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
        <Dropdown v-model="v$.values.single_select_default.$model">
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
import { notifyIf } from '@baserow/modules/core/utils/error'
import form from '@baserow/modules/core/mixins/form'
import fieldSubForm from '@baserow/modules/database/mixins/fieldSubForm'
import FieldSelectOptions from '@baserow/modules/database/components/field/FieldSelectOptions'
import FieldService from '@baserow/modules/database/services/field'
import { randomColor } from '@baserow/modules/core/utils/colors'
import { useVuelidate } from '@vuelidate/core'

export default {
  name: 'FieldSingleSelectOptionsSubForm',
  components: { FieldSelectOptions },
  mixins: [form, fieldSubForm],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      loading: false,
      allowedValues: ['select_options', 'single_select_default'],
      values: {
        select_options: [],
        single_select_default: null,
      },
    }
  },
  watch: {
    fieldType() {
      this.checkFetchOptions()
    },
  },
  mounted() {
    this.checkFetchOptions()
  },
  methods: {
    isFormValid() {
      this.$refs.selectOptions.v$.$touch()
      return !this.$refs.selectOptions.v$.$invalid
    },
    checkFetchOptions() {
      if (
        this.fieldType &&
        this.defaultValues.type &&
        this.defaultValues.type !== this.fieldType &&
        this.$registry
          .get('field', this.defaultValues.type)
          .shouldFetchFieldSelectOptions()
      ) {
        this.fetchOptions()
      }
    },
    async fetchOptions() {
      this.loading = true
      const splitCommaSeparated = this.$registry
        .get('field', this.fieldType)
        .acceptSplitCommaSeparatedSelectOptions()
      this.values.select_options = []
      const usedColors = []
      try {
        const { data } = await FieldService(this.$client).getUniqueRowValues(
          this._props.defaultValues.id,
          this.$config.BASEROW_UNIQUE_ROW_VALUES_SIZE_LIMIT,
          splitCommaSeparated
        )
        for (const value of data.values) {
          const color = randomColor(usedColors)
          usedColors.push(color)
          this.values.select_options.push({
            value,
            color,
          })
        }
      } catch (e) {
        notifyIf(e)
      }
      this.loading = false
    },
  },
  validations() {
    return {
      values: {
        single_select_default: {},
      },
    }
  },
}
</script>
