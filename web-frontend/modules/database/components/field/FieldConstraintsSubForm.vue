<template>
  <div>
    <FormGroup
      :label="$t('fieldConstraintsSubform.title')"
      :small-label="true"
      :horizontal-narrow="true"
      class="margin-bottom-2"
    >
      <div class="control__elements flex justify-content-end">
        <ButtonText
          v-if="
            !disabled && hasAvailableConstraints && !hasConflictingConstraints
          "
          :disabled="allConstraintsAdded || hasDisabledFieldConstraints"
          tag="a"
          icon="iconoir-plus"
          @click.prevent="addConstraint"
        >
          {{ $t('fieldConstraintsSubform.addConstraint') }}
        </ButtonText>
      </div>
    </FormGroup>

    <div class="control__messages padding-top-0">
      <p
        v-if="disabled"
        class="control__helper-text control__helper-text--warning"
      >
        {{ $t('fieldConstraintsSubform.readonlyFieldMessage') }}
      </p>
      <p
        v-else-if="hasConflictingConstraints"
        class="control__helper-text control__helper-text--warning"
      >
        {{
          $t('fieldConstraintsSubform.noConstraintsCompatibleWithDefaultValue')
        }}
      </p>
      <p
        v-else-if="hasDisabledFieldConstraints"
        class="control__helper-text control__helper-text--warning"
      >
        {{
          $t('fieldConstraintsSubform.noConstraintsCompatibleWithDefaultValue')
        }}
      </p>
      <p
        v-else-if="hasAvailableConstraints && !hasDisabledFieldConstraints"
        class="control__helper-text"
      >
        {{ $t('fieldConstraintsSubform.description') }}
      </p>
      <p v-else class="control__helper-text control__helper-text--warning">
        {{ $t('fieldConstraintsSubform.noConstraintsAvailable') }}
      </p>
    </div>

    <FieldConstraintItems
      v-if="hasAvailableConstraints && !hasDisabledFieldConstraints"
      :value="value"
      :field="field"
      :disabled="disabled"
      :error="error"
      :field-default-value="fieldDefaultValue"
      @input="$emit('input', $event)"
    />
  </div>
</template>

<script>
import BigNumber from 'bignumber.js'
import ButtonText from '@baserow/modules/core/components/ButtonText'
import FormGroup from '@baserow/modules/core/components/FormGroup'
import FieldConstraintItems from '@baserow/modules/database/components/field/FieldConstraintItems.vue'

export default {
  name: 'FieldConstraintsSubForm',
  components: { ButtonText, FormGroup, FieldConstraintItems },
  props: {
    value: {
      type: Array,
      required: true,
    },
    fieldDefaultValue: {
      type: [String, Number, Boolean, BigNumber],
      required: false,
      default: null,
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
    hasAvailableConstraints() {
      return this.allowedConstraintTypes.length > 0
    },
    hasDisabledFieldConstraints() {
      return false
    },
    allConstraintsAdded() {
      const addedConstraintNames = this.value.map(
        (constraint) => constraint.type_name
      )
      return this.allowedConstraintTypes.every((constraintType) =>
        addedConstraintNames.includes(constraintType.getTypeName())
      )
    },
    hasConflictingConstraints() {
      const defaultValue = this.fieldDefaultValue

      if (!defaultValue) {
        return false
      }

      const constraintsThatSupportDefaultValue =
        this.allowedConstraintTypes.filter((constraintType) =>
          constraintType.canSupportDefaultValue()
        )

      return (
        this.allowedConstraintTypes.length > 0 &&
        constraintsThatSupportDefaultValue.length === 0
      )
    },
  },
  methods: {
    addConstraint() {
      const hasEmptyConstraint = this.value.some(
        (constraint) => constraint.type_name === ''
      )
      if (hasEmptyConstraint) {
        return
      }

      const availableConstraintTypes =
        this.getAvailableConstraintTypesForNewConstraint()
      const firstAvailableType =
        availableConstraintTypes.length > 0 ? availableConstraintTypes[0] : null

      if (!firstAvailableType) {
        return
      }

      const newConstraint = {
        type_name: firstAvailableType.getTypeName(),
      }
      const updatedConstraints = [...this.value, newConstraint]
      this.$emit('input', updatedConstraints)
    },
    getAvailableConstraintTypesForNewConstraint() {
      const selectedNames = this.value
        .map((constraint) => constraint.type_name)
        .filter((name) => name)

      return this.allowedConstraintTypes.filter((constraintType) => {
        const constraintName = constraintType.getTypeName()
        return !selectedNames.includes(constraintName)
      })
    },
  },
}
</script>
