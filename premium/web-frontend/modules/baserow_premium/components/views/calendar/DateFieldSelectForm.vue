<template>
  <div>
    <form v-if="dateFields.length > 0" @submit.prevent="submit">
      <FormGroup
        :label="$t('dateFieldSelectForm.dateField')"
        small-label
        :error="fieldHasErrors('dateFieldId')"
        required
      >
        <Dropdown v-model="v$.values.dateFieldId.$model" :show-search="true">
          <DropdownItem
            v-for="dateField in dateFields"
            :key="dateField.id"
            :name="dateField.name"
            :value="dateField.id"
            :icon="fieldIcon(dateField.type)"
          >
          </DropdownItem>
        </Dropdown>

        <template #error>
          {{ v$.values.dateFieldId.$errors[0]?.$message }}
        </template>
      </FormGroup>
      <slot></slot>
    </form>
    <p v-else>
      {{ $t('dateFieldSelectForm.noCompatibleDateFields') }}
    </p>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required, helpers } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'DateFieldSelectForm',
  mixins: [form],
  props: {
    table: {
      type: Object,
      required: true,
    },
    dateFields: {
      type: Array,
      required: true,
    },
    dateFieldId: {
      type: Number,
      required: false,
      default: null,
    },
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      values: {
        dateFieldId: null,
      },
    }
  },
  mounted() {
    this.values.dateFieldId =
      this.dateFieldId || (this.dateFields.length > 0 && this.dateFields[0]?.id)
  },
  methods: {
    fieldIcon(type) {
      const ft = this.$registry.get('field', type)
      return ft?.getIconClass() || 'calendar-alt'
    },
  },
  validations() {
    return {
      values: {
        dateFieldId: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
      },
    }
  },
}
</script>
