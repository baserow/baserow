<template>
  <div>
    <FieldConstraintItem
      v-for="(constraint, index) in constraints"
      :key="index"
      :constraint="constraint"
      :index="index"
      :field="field"
      :disabled="disabled"
      :error="error"
      :allowed-constraint-types="getAvailableConstraintTypes(index)"
      @update="updateConstraint"
      @remove="removeConstraint"
    />
  </div>
</template>

<script>
import FieldConstraintItem from '@baserow/modules/database/components/field/FieldConstraintItem.vue'

export default {
  name: 'FieldConstraintItems',
  components: { FieldConstraintItem },
  props: {
    value: {
      type: Array,
      required: true,
    },
    field: {
      type: Object,
      required: true,
    },
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
    error: {
      type: String,
      required: false,
      default: null,
    },
  },
  computed: {
    constraints: {
      get() {
        return this.value || []
      },
      set(value) {
        this.$emit('input', value)
      },
    },
    constraintTypes() {
      return this.$registry.getAll('fieldConstraint')
    },
    allowedConstraintTypes() {
      return Object.values(this.constraintTypes).filter((constraintType) => {
        return constraintType
          .getCompatibleFieldTypes()
          .includes(this.field.type)
      })
    },
  },
  methods: {
    getAvailableConstraintTypes(currentIndex) {
      const selectedTypes = this.constraints
        .map((constraint, index) => ({ type: constraint.type, index }))
        .filter(({ type, index }) => type && index !== currentIndex)
        .map(({ type }) => type)

      return this.allowedConstraintTypes.filter((constraintType) => {
        return !selectedTypes.includes(constraintType.type)
      })
    },
    removeConstraint(index) {
      this.constraints = this.constraints.filter((_, i) => i !== index)
    },
    updateConstraint(index, updates) {
      const updatedConstraints = [...this.constraints]
      updatedConstraints[index] = { ...updatedConstraints[index], ...updates }
      this.constraints = updatedConstraints
    },
  },
}
</script>
