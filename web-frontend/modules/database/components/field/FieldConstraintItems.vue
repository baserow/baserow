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
import BigNumber from 'bignumber.js'

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
    fieldDefaultValue: {
      type: [String, Number, Boolean, BigNumber],
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
    getAvailableConstraintTypes(index) {
      const selectedNames = this.constraints
        .map((constraint, i) => (i === index ? null : constraint.type_name))
        .filter((name) => name)

      return this.allowedConstraintTypes.map((constraintType) => {
        const constraintName = constraintType.getTypeName()
        const isSelected = selectedNames.includes(constraintName)
        const isDisabled =
          this.fieldDefaultValue && !constraintType.canSupportDefaultValue()

        return Object.assign(constraintType, {
          isDisabled: isSelected || isDisabled,
        })
      })
    },
    updateConstraint(index, constraint) {
      const updatedConstraints = [...this.constraints]
      updatedConstraints[index] = constraint
      this.$emit('input', updatedConstraints)
    },
    removeConstraint(index) {
      const updatedConstraints = this.constraints.filter((_, i) => i !== index)
      this.$emit('input', updatedConstraints)
    },
  },
}
</script>
