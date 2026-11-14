import _ from 'lodash'
import { clone } from '@baserow/modules/core/utils/object'

const FILTER_KEYS = ['filters', 'filter_groups', 'filter_type']

/**
 * Keeps the filters of an open Local Baserow service form in sync with the saved
 * service. A form only reads its default values when it's created, so filters
 * saved elsewhere (another user, an undo, or Kuma) would otherwise not show, and
 * saving the form would put the old filters back.
 *
 * Saved filter changes are only copied into the form when the user hasn't edited
 * the filters themselves, so unsaved edits are never lost. Other values are never
 * touched.
 *
 * The mixin also provides `serviceFilters` to the filter form's descendants, to
 * find out whether the filters or the table have unsaved changes.
 */
export default {
  provide() {
    return {
      serviceFilters: {
        hasUnsavedChanges: () => this.serviceFiltersHaveUnsavedChanges(),
        // Another table than the saved one was picked.
        hasUnsavedTableChange: () =>
          this.getServiceFiltersTableChange() === 'changed',
        // The table picked when none is saved yet, or null.
        getUnsavedTableId: () =>
          this.getServiceFiltersTableChange() === 'picked'
            ? this.values.table_id
            : null,
      },
    }
  },
  computed: {
    savedServiceFilters() {
      const source = this.getServiceFiltersSource()
      if (!source) {
        return null
      }
      return Object.fromEntries(
        FILTER_KEYS.filter((key) => key in source).map((key) => [
          key,
          source[key],
        ])
      )
    },
  },
  watch: {
    savedServiceFilters(saved, previous) {
      if (!saved || !previous || !this.values) {
        return
      }
      const keysToSync = this.getSyncedServiceFilterKeys(saved).filter(
        (key) =>
          !_.isEqual(saved[key], previous[key]) &&
          // The user edited these filters, keep their changes.
          _.isEqual(this.values[key], previous[key])
      )
      this.setServiceFilterValues(keysToSync, saved)
    },
  },
  methods: {
    /**
     * Returns the saved object holding the service's filters. Can be overridden
     * when it isn't the `service` prop.
     */
    getServiceFiltersSource() {
      return this.service
    },
    getSyncedServiceFilterKeys(saved) {
      return FILTER_KEYS.filter((key) => key in saved && key in this.values)
    },
    serviceFiltersHaveUnsavedChanges() {
      const saved = this.savedServiceFilters
      if (!saved || !this.values) {
        return false
      }
      return this.getSyncedServiceFilterKeys(saved).some(
        (key) => !_.isEqual(this.values[key], saved[key])
      )
    },
    /**
     * Returns how the form's table differs from the saved one: `picked` when none
     * is saved yet, `changed` when another one is saved, or null when it doesn't.
     */
    getServiceFiltersTableChange() {
      const source = this.getServiceFiltersSource()
      if (
        !source ||
        !this.values ||
        !('table_id' in source) ||
        !('table_id' in this.values)
      ) {
        return null
      }
      const tableId = this.values.table_id ?? null
      const savedTableId = source.table_id ?? null
      if (tableId === null || tableId === savedTableId) {
        return null
      }
      return savedTableId === null ? 'picked' : 'changed'
    },
    setServiceFilterValues(keys, saved) {
      if (!keys.length) {
        return
      }
      // The values now match what's saved, so there is nothing to emit or save.
      this.skipFirstValuesEmit = true
      keys.forEach((key) => {
        this.values[key] = clone(saved[key])
      })
    },
  },
}
