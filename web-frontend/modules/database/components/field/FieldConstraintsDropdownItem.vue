<template>
  <div class="field-constraints-options__item">
    <div class="field-constraints-options__row">
      <div class="field-constraints-options__value">
        <Dropdown
          :value="constraint.type"
          :disabled="disabled"
          :fixed-items="true"
          @input="updateConstraintType"
        >
          <DropdownItem
            v-for="constraintType in allowedConstraintTypes"
            :key="constraintType.type"
            :name="constraintType.getName()"
            :value="constraintType.type"
          ></DropdownItem>
        </Dropdown>
      </div>

      <div v-if="getConstraintParametersComponent(constraint.type)">
        <component
          :is="getConstraintParametersComponent(constraint.type)"
          :constraint="constraint"
          :field="field"
          :disabled="disabled"
          @input="updateConstraintValue"
        />
      </div>

      <ButtonIcon
        tag="a"
        icon="iconoir-bin"
        @click.stop.prevent="removeConstraint"
      ></ButtonIcon>
    </div>

    <div v-if="error" class="control__messages padding-top-1">
      <p class="control__messages--error field-context__inner-element-width">
        {{ getErrorMessage() }}
      </p>
    </div>
  </div>
</template>

<script>
import ButtonIcon from '@baserow/modules/core/components/ButtonIcon'

export default {
  name: 'FieldConstraintsDropdownItem',
  components: { ButtonIcon },
  props: {
    constraint: {
      type: Object,
      required: true,
    },
    index: {
      type: Number,
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
    allowedConstraintTypes: {
      type: Array,
      required: true,
    },
    error: {
      type: String,
      required: false,
      default: null,
    },
  },
  methods: {
    updateConstraintType(type) {
      this.$emit('update', this.index, { type })
    },
    updateConstraintValue(value) {
      this.$emit('update', this.index, { value })
    },
    removeConstraint() {
      this.$emit('remove', this.index)
    },
    getConstraintParametersComponent(constraintType) {
      if (!constraintType) {
        return null
      }
      const constraintTypeInstance = this.$registry.get(
        'fieldConstraint',
        constraintType
      )
      return constraintTypeInstance?.getParametersComponent()
    },
    getErrorMessage() {
      if (!this.error) {
        return ''
      }

      const constraintTypeInstance = this.$registry.get(
        'fieldConstraint',
        this.constraint.type
      )
      return constraintTypeInstance.getErrorMessage(this.error)
    },
  },
}
</script>
