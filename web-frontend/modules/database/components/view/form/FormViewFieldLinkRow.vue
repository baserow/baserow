<template>
  <div class="control__elements">
    <PaginatedDropdown
      :fetch-page="fetchPage"
      :value="dropdownValue"
      :initial-display-name="initialDisplayName"
      :error="touched && !valid"
      :fetch-on-open="lazyLoad"
      :disabled="readOnly"
      :include-display-name-in-selected-event="true"
      :value-name="'label'"
      @input="updateValue($event)"
      @hide="touch()"
    ></PaginatedDropdown>
    <div v-show="touched && !valid" class="error">
      {{ error }}
    </div>
  </div>
</template>

<script>
import PaginatedDropdown from '@baserow/modules/core/components/PaginatedDropdown'
import rowEditField from '@baserow/modules/database/mixins/rowEditField'
import ViewService from '@baserow/modules/database/services/view'

export default {
  name: 'FormViewFieldLinkRow',
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
  computed: {
    dropdownValue() {
      return this.value.length === 0 ? false : this.value[0].id
    },
    initialDisplayName() {
      return this.value.length === 0 ? '' : this.rowDisplayName(this.value[0])
    },
  },
  methods: {
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
      response.data.results.forEach((row) => {
        this.rowLookup[row.id] = row
      })
      response.data.results = response.data.results.map((row) => ({
        ...row,
        label: this.rowDisplayName(row),
      }))
      return response
    },
    updateValue({ value, displayName }) {
      if (value === null || value === '') {
        this.$emit('update', [], this.value)
        return
      }
      // Store the original row value (e.g. '' for empty primary fields) so
      // conditional visibility checks work correctly. Fall back to displayName
      // if the row isn't in the cache (e.g. pre-existing selection).
      const originalRow = this.rowLookup[value]
      const selection = [
        {
          id: value,
          value: originalRow ? originalRow.value : displayName,
        },
      ]
      this.$emit('update', selection, this.value)
    },
  },
}
</script>
