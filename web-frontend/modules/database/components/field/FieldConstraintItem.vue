<template>
  <div class="field-constraints-options__item">
    <div class="field-constraints-options__row">
      <div class="field-constraints-options__value">
        <Dropdown
          :value="constraint.name"
          :disabled="disabled"
          :fixed-items="true"
          @input="updateConstraintName"
        >
          <DropdownItem
            v-for="constraintType in allowedConstraintTypes"
            :key="constraintType.type"
            :name="constraintType.getLabel()"
            :value="constraintType.getName() || constraintType.type"
          ></DropdownItem>
        </Dropdown>
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
  name: 'FieldConstraintItem',
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
    updateConstraintName(name) {
      this.$emit('update', this.index, { name })
    },
    removeConstraint() {
      this.$emit('remove', this.index)
    },
    getErrorMessage() {
      if (!this.error) {
        return ''
      }

      const constraintTypeInstance = this.$registry.get(
        'fieldConstraint',
        this.constraint.name
      )
      return (
        constraintTypeInstance?.getErrorMessage(this.error) ||
        this.$t('fieldConstraintsSubform.errorGenericData')
      )
    },
  },
}
</script>
