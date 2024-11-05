<template>
  <form @submit.prevent="submit">
    <FormGroup
      small-label
      :label="$t('viewForm.name')"
      required
      :error="fieldHasErrors('name')"
      class="margin-bottom-2"
    >
      <FormInput
        ref="name"
        v-model="values.name"
        size="large"
        :error="fieldHasErrors('name')"
        @focus.once="$event.target.select()"
        @blur="v$.values.name.$touch()"
      >
      </FormInput>

      <template #error>
        {{ $t('error.requiredField') }}
      </template>
    </FormGroup>

    <FormGroup small-label :label="$t('viewForm.whoCanEdit')" required>
      <component
        :is="type.getRadioComponent()"
        v-for="type in availableViewOwnershipTypesForCreation"
        :key="type.getType()"
        class="margin-right-2"
        :view-ownership-type="type"
        :database="database"
        :selected-type="values.ownershipType"
        @input="(value) => (values.ownershipType = value)"
      >
      </component>
    </FormGroup>

    <slot></slot>
  </form>
</template>

<script>
import { required } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'
import Radio from '@baserow/modules/core/components/Radio'

export default {
  name: 'ViewForm',
  components: { Radio },
  mixins: [form],
  props: {
    defaultName: {
      type: String,
      required: false,
      default: '',
    },
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      values: {
        name: this.defaultName,
        ownershipType: 'collaborative',
      },
    }
  },
  computed: {
    viewOwnershipTypes() {
      return Object.values(this.$registry.getAll('viewOwnershipType'))
    },
    availableViewOwnershipTypesForCreation() {
      return this.activeViewOwnershipTypes.filter((t) =>
        t.userCanTryCreate(this.table, this.database.workspace.id)
      )
    },
    activeViewOwnershipTypes() {
      return this.sortOwnershipTypes(this.viewOwnershipTypes)
    },
  },
  mounted() {
    this.$refs.name.focus()
    const firstAndHenceDefaultOwnershipType =
      this.availableViewOwnershipTypesForCreation[0]?.getType()
    this.values.ownershipType =
      this.defaultValues.ownershipType || firstAndHenceDefaultOwnershipType
  },
  methods: {
    sortOwnershipTypes(ownershipTypes) {
      return ownershipTypes
        .slice()
        .sort((a, b) => b.getListViewTypeSort() - a.getListViewTypeSort())
    },
  },
  validations: {
    values: {
      name: { required },
    },
  },
}
</script>
