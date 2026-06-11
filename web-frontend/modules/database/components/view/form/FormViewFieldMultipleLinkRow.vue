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
          :value-name="'label'"
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
import ViewService from '@baserow/modules/database/services/view'
import { clone } from '@baserow/modules/core/utils/object'

export default {
  name: 'FormViewFieldMultipleLinkRow',
  components: { PaginatedDropdown },
  mixins: [rowEditField],
  props: {
    slug: {
      type: String,
      required: true,
    },
    /**
     * In some cases, for example in the form view preview, we only want to fetch the
     * first related rows after the user has opened the dropdown. This will prevent a
     * race condition where the enabled state of the field might not yet been updated
     * before we fetch the related rows. If the state has not yet been changed in the
     * backend, it will result in an error.
     */
    lazyLoad: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['update'],
  data() {
    return {
      /** Map of row id → original row object, populated by fetchPage. */
      rowLookup: {},
    }
  },
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
    rowDisplayName(row) {
      if (row.value) {
        return row.value
      }
      if (!Number.isInteger(row.id)) {
        return row.value
      }
      return this.$t('functionnalGridViewFieldLinkRow.unnamed', {
        value: row.id,
      })
    },
    async fetchPage(page, search) {
      const publicAuthToken =
        this.$store.getters['page/view/public/getAuthToken']
      const response = await ViewService(this.$client).linkRowFieldLookup(
        this.slug,
        this.field.id,
        page,
        search,
        100,
        publicAuthToken
      )
      // Cache original rows so updateValue can store the real value
      // (not the display label) to preserve conditional visibility checks.
      // A first-page fetch means a new search or a reopened dropdown, so the
      // previous result set can no longer be picked; reset the cache to
      // prevent it from growing unboundedly.
      if (page === 1) {
        this.rowLookup = {}
      }
      response.data.results.forEach((row) => {
        this.rowLookup[row.id] = row
      })
      response.data.results = response.data.results.map((row) => ({
        ...row,
        label: this.rowDisplayName(row),
      }))
      return response
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
    updateValue({ value, displayName }, index) {
      const newValue = clone(this.value)
      // Store the original row value (e.g. '' for empty primary fields) so
      // conditional visibility checks work correctly. Fall back to displayName
      // if the row isn't in the cache (e.g. pre-existing selection).
      if (value === null || value === '') {
        newValue[index] = { id: value, value: '' }
      } else {
        const originalRow = this.rowLookup[value]
        newValue[index] = {
          id: value,
          value: originalRow ? originalRow.value : displayName,
        }
      }
      this.$emit('update', newValue, this.value)
    },
  },
}
</script>
