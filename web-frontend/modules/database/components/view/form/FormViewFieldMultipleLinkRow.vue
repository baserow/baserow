<template>
  <div class="control__elements">
    <div
      v-for="(v, index) in value"
      :key="index + '-' + value[index].id"
      class="margin-bottom-2 flex"
    >
      <div class="flex-100">
        <PaginatedDropdown
          :fetch-page="fetchPage"
          :value="value[index].id"
          :add-empty-item="false"
          :initial-display-name="rowDisplayName(value[index])"
          :error="touched && !valid && isInvalidValue(value[index])"
          :fetch-on-open="lazyLoad"
          :disabled="readOnly"
          :include-display-name-in-selected-event="true"
          :value-name="rowDisplayName"
          @input="updateValue($event, index)"
        ></PaginatedDropdown>
      </div>
      <div class="align-right">
        <Button
          type="secondary"
          tag="a"
          icon="iconoir-bin"
          @click="remove(index)"
        ></Button>
      </div>
    </div>
    <div>
      <Button
        type="secondary"
        tag="a"
        icon="iconoir-plus"
        @click="add"
      ></Button>
    </div>
    <div v-show="touched && !valid" class="error">
      {{ error }}
    </div>
  </div>
</template>

<script>
import PaginatedDropdown from '@baserow/modules/core/components/PaginatedDropdown'
import baseField from '@baserow/modules/database/mixins/baseField'
import rowEditField from '@baserow/modules/database/mixins/rowEditField'
import formViewLinkRowField from '@baserow/modules/database/mixins/formViewLinkRowField'
import { clone } from '@baserow/modules/core/utils/object'

export default {
  name: 'FormViewFieldMultipleLinkRow',
  components: { PaginatedDropdown },
  mixins: [rowEditField, formViewLinkRowField],
  emits: ['update'],
  created() {
    if (this.value.length === 0 && this.required) {
      this.add()
    }
  },
  methods: {
    getValidationError(value) {
      // A slot counts as filled only if it holds a row with a real id. This also
      // flags a placeholder slot (added but never picked) as invalid, even when
      // the field is optional.
      const valueArr = Array.isArray(value) ? value : []
      const hasInvalidSlot = valueArr.some((v) => this.isInvalidValue(v))
      // A placeholder slot is always invalid, and a required field also needs at
      // least one slot.
      if (hasInvalidSlot || (this.required && valueArr.length === 0)) {
        return this.$t('error.requiredField')
      }
      // Delegate to baseField, not rowEditField (the other mixin): rowEditField
      // would re-run its own required check, which we've already handled above.
      return baseField.methods.getValidationError.call(this, value)
    },
    isInvalidValue(value) {
      return !Number.isInteger(value.id)
    },
    add() {
      const newValue = clone(this.value)
      newValue.push({
        id: false,
        value: '',
      })
      this.$emit('update', newValue, this.value)
    },
    remove(index) {
      const newValue = clone(this.value)
      newValue.splice(index, 1)
      this.$emit('update', newValue, this.value)
    },
    updateValue({ value, displayName, item }, index) {
      const newValue = clone(this.value)
      if (value === null || value === '') {
        newValue[index] = { id: value, value: '' }
      } else {
        newValue[index] = {
          id: value,
          value: this.resolveRowValue(item, displayName),
        }
      }
      this.$emit('update', newValue, this.value)
    },
  },
}
</script>
