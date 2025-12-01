import fieldSubForm from '@baserow/modules/database/mixins/fieldSubForm'
import { notifyIf } from '@baserow/modules/core/utils/error'
import form from '@baserow/modules/core/mixins/form'
import FieldSelectOptions from '@baserow/modules/database/components/field/FieldSelectOptions'
import FieldService from '@baserow/modules/database/services/field'
import { randomColor } from '@baserow/modules/core/utils/colors'

export default {
  mixins: [form, fieldSubForm],
  components: { FieldSelectOptions },
  watch: {
    fieldType() {
      this.checkFetchOptions()
    },
  },
  mounted() {
    this.checkFetchOptions()
  },
  data() {
    return {
      loading: false,
      allowedValues: ['select_options'],
      values: {
        select_options: [],
      },
    }
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
}
