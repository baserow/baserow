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
      // A picked row with an empty primary stores value:'' so that conditional
      // visibility ("is not empty") correctly treats it as empty. That makes
      // fieldType.isEmpty return true even when the user *did* select rows,
      // which would falsely fail required validation. Treat "filled in" as
      // "every slot contains a row with a real id", regardless of primary.
      const valueArr = Array.isArray(value) ? value : []
      const hasInvalidSlot = valueArr.some((v) => this.isInvalidValue(v))
      if (this.required && (valueArr.length === 0 || hasInvalidSlot)) {
        return this.$t('error.requiredField')
      }
      if (!this.required && hasInvalidSlot) {
        return this.$t('error.requiredField')
      }
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
      // Store the original row value (e.g. '' for empty primary fields) so
      // conditional visibility checks keep working. Fall back to displayName if
      // the dropdown couldn't resolve the row (e.g. a pre-existing selection
      // that isn't in the current results).
      if (value === null || value === '') {
        newValue[index] = { id: value, value: '' }
      } else {
        newValue[index] = { id: value, value: item ? item.value : displayName }
      }
      this.$emit('update', newValue, this.value)
    },
  },
}
</script>
