<template>
  <div v-if="hasAvailableConstraints">
    <FormGroup
      :label="$t('fieldConstraintsSubform.title')"
      :small-label="true"
      :horizontal="true"
      class="control--horizontal-narrow margin-bottom-2 field-constraints__title"
    >
      <div class="control__elements flex justify-content-end">
        <ButtonText
          v-if="!disabled"
          :disabled="allConstraintsAdded"
          icon="iconoir-plus"
          @click.prevent="addConstraint"
        >
          {{ $t('fieldConstraintsSubform.addConstraint') }}
        </ButtonText>
      </div>
    </FormGroup>

    <div class="control__messages padding-top-0">
      <p class="control__helper-text">
        {{ $t('fieldConstraintsSubform.description') }}
      </p>
    </div>

    <FieldConstraintsDropdown
      :value="value"
      :field="field"
      :disabled="disabled"
      :error="error"
      @input="$emit('input', $event)"
      @constraint-removed="$emit('constraint-removed', $event)"
      @constraint-updated="$emit('constraint-updated', $event)"
    />
  </div>
</template>

<script>
import ButtonText from '@baserow/modules/core/components/ButtonText'
import FormGroup from '@baserow/modules/core/components/FormGroup'
import FieldConstraintsDropdown from './FieldConstraintsDropdown.vue'

export default {
  name: 'FieldConstraintsSubForm',
  components: { ButtonText, FormGroup, FieldConstraintsDropdown },
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
        return constraintType.fieldIsCompatible(this.field)
      })
    },
    hasAvailableConstraints() {
      return this.allowedConstraintTypes.length > 0
    },
    allConstraintsAdded() {
      const addedConstraintTypes = this.value.map(
        (constraint) => constraint.type
      )
      return this.allowedConstraintTypes.every((constraintType) =>
        addedConstraintTypes.includes(constraintType.type)
      )
    },
  },
  methods: {
    addConstraint() {
      const hasEmptyConstraint = this.value.some(
        (constraint) => constraint.type === ''
      )
      if (hasEmptyConstraint) {
        return
      }

      const availableConstraintTypes =
        this.getAvailableConstraintTypesForNewConstraint()
      const firstAvailableType =
        availableConstraintTypes.length > 0
          ? availableConstraintTypes[0].type
          : ''

      const newConstraint = {
        type: firstAvailableType,
        params: {},
      }
      const updatedConstraints = [...this.value, newConstraint]
      this.$emit('input', updatedConstraints)
      this.$emit('constraint-added', newConstraint)
    },
    getAvailableConstraintTypesForNewConstraint() {
      const selectedTypes = this.value
        .map((constraint) => constraint.type)
        .filter((type) => type)

      return this.allowedConstraintTypes.filter((constraintType) => {
        return !selectedTypes.includes(constraintType.type)
      })
    },
  },
}
</script>
