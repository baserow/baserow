<template>
  <form @submit.prevent="submit">
    <FormGroup
      small-label
      :label="$t('viewForm.name')"
      required
      :error="v$.name.$error"
      class="margin-bottom-2"
    >
      <FormInput
        ref="name"
        v-model="v$.name.$model"
        size="large"
        :error="v$.name.$error"
        @focus.once="$event.target.select()"
        @blur="v$.name.$touch"
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
        :selected-type="v$.ownershipType.$model"
        @input="(value) => (values.ownershipType = value)"
      >
      </component>
    </FormGroup>

    <slot></slot>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
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
        ownershipType: 'collaborative',
      },
      v$: null,
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
  created() {
    const values = reactive({
      name: this.defaultName,
      ownershipType: 'collaborative',
    })

    const rules = computed(() => ({
      name: { required },
      ownershipType: { required },
    }))
    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
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
}
</script>
