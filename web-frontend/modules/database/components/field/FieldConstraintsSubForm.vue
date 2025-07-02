<template>
  <div>
    <FormGroup
      :label="$t('fieldConstraintsSubform.title')"
      :small-label="true"
      :horizontal="true"
      class="control--horizontal-narrow margin-bottom-2 field-constraints__title"
    >
      <div class="control__elements flex justify-content-end">
        <ButtonText
          v-if="!disabled && hasAvailableConstraints"
          :disabled="allConstraintsAdded"
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
      <p v-else-if="hasAvailableConstraints" class="control__helper-text">
        {{ $t('fieldConstraintsSubform.description') }}
      </p>
      <p v-else class="control__helper-text control__helper-text--warning">
        {{ $t('fieldConstraintsSubform.noConstraintsAvailable') }}
      </p>
    </div>

    <FieldConstraintItems
      v-if="hasAvailableConstraints"
      :value="value"
      :field="field"
      :disabled="disabled"
      :error="error"
      @input="$emit('input', $event)"
    />
  </div>
</template>

<script>
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
    allConstraintsAdded() {
      const addedConstraintNames = this.value.map(
        (constraint) => constraint.name
      )
      return this.allowedConstraintTypes.every((constraintType) =>
        addedConstraintNames.includes(
          constraintType.getName() || constraintType.type
        )
      )
    },
  },
  methods: {
    addConstraint() {
      const hasEmptyConstraint = this.value.some(
        (constraint) => constraint.name === ''
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
        name: firstAvailableType.getName() || firstAvailableType.type,
      }
      const updatedConstraints = [...this.value, newConstraint]
      this.$emit('input', updatedConstraints)
    },
    getAvailableConstraintTypesForNewConstraint() {
      const selectedNames = this.value
        .map((constraint) => constraint.name)
        .filter((name) => name)

      return this.allowedConstraintTypes.filter((constraintType) => {
        const constraintName = constraintType.getName() || constraintType.type
        return !selectedNames.includes(constraintName)
      })
    },
  },
}
</script>
