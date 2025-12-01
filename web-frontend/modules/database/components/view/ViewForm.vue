<template>
  <form @submit.prevent="submit">
    <FormGroup
      small-label
      :label="$t('viewForm.name')"
      required
      :error="v$.values.name.$error"
      class="margin-bottom-2"
    >
      <FormInput
        ref="name"
        v-model="v$.values.name.$model"
        size="large"
        :error="fieldHasErrors('name')"
        @focus.once="$event.target.select()"
      >
      </FormInput>

      <template #error>
        <span v-if="v$.values.name.required.$invalid">
          {{ $t('error.requiredField') }}
        </span>
      </template>
    </FormGroup>

    <FormGroup small-label :label="$t('viewForm.whoCanEdit')" required>
      <Dropdown v-model="values.ownershipType" size="large" :fixed-items="true">
        <DropdownItem
          v-for="type in availableViewOwnershipTypesForCreation"
          :key="type.getType()"
          :name="type.getName()"
          :value="type.getType()"
          :icon="
            type.isDeactivated(database.workspace.id)
              ? 'iconoir-lock'
              : type.getIconClass()
          "
          :description="type.getDescription()"
          :disabled="type.isDeactivated(database.workspace.id)"
          @click="clickOnDeactivatedItem($event, type)"
        ></DropdownItem>
      </Dropdown>
    </FormGroup>
    <component
      :is="
        type.isDeactivated(database.workspace.id)
          ? type.getDeactivatedModal()[0]
          : null
      "
      v-for="type in availableViewOwnershipTypesForCreation"
      :key="type.getType()"
      :ref="'deactivatedClickModal-' + type.getType()"
      v-bind="
        type.isDeactivated(database.workspace.id)
          ? type.getDeactivatedModal()[1]
          : null
      "
      :workspace="database.workspace"
    ></component>
    <slot></slot>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { reactive } from 'vue'
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

  setup() {
    const values = reactive({
      values: {
        name: '',
        ownershipType: 'collaborative',
      },
    })

    const rules = {
      values: {
        name: { required },
        ownershipType: {},
      },
    }

    return {
      values: values.values,
      v$: useVuelidate(rules, values, { $lazy: true }),
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
    this.values.name = this.defaultName
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
    clickOnDeactivatedItem(event, type) {
      if (type.isDeactivated(this.database.workspace.id)) {
        this.$refs[`deactivatedClickModal-${type.getType()}`][0].show()
      }
    },
  },
}
</script>
