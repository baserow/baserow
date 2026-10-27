import { DataProviderType } from '@baserow/modules/core/dataProviderTypes'
import { getValueAtPath } from '@baserow/modules/core/utils/object'
import {
  getDashboardFilterValues,
  isDashboardFilterPath,
} from '@baserow/modules/dashboard/utils/filter'

export class DashboardFilterDataProviderType extends DataProviderType {
  static getType() {
    return 'dashboard_filter'
  }

  isValid(path) {
    return isDashboardFilterPath(path)
  }

  get name() {
    return this.app.$i18n.t('dashboardFilter.providerName')
  }

  getDataContent(context) {
    const { storePrefix = '' } = context
    const getters = this.app.$store.getters
    const prefix = `${storePrefix}dashboardApplication/`
    return Object.fromEntries(
      getters[prefix + 'getFilters'].map((filter) => [
        filter.id,
        this.getDataChunk(context, [String(filter.id)]),
      ])
    )
  }

  getDataChunk({ storePrefix = '' }, path) {
    const getters = this.app.$store.getters
    const prefix = `${storePrefix}dashboardApplication/`
    const filter = getters[prefix + 'getFilters'].find(
      ({ id }) => String(id) === path[0]
    )
    if (!filter) return null
    const values = getDashboardFilterValues(
      filter,
      getters[prefix + 'getAppliedFilterValues'](filter.id)
    )
    // Saved explicit selectors keep their list semantics after a format change.
    if (path.length > 1) return getValueAtPath(values, path.slice(1))
    return filter.mode === 'dropdown' && filter.multiple
      ? values
      : values[0] || ''
  }

  getDataSchema({ storePrefix = '' }) {
    const filters =
      this.app.$store.getters[`${storePrefix}dashboardApplication/getFilters`]
    return {
      type: 'object',
      properties: Object.fromEntries(
        filters.map((filter, index) => [
          filter.id,
          {
            title: filter.label,
            order: index,
            ...(filter.mode === 'dropdown' && filter.multiple
              ? { type: 'array', items: { type: 'string' } }
              : { type: 'string' }),
          },
        ])
      ),
    }
  }

  getNodes(context) {
    const root = super.getNodes(context)
    const { storePrefix = '' } = context
    const filters =
      this.app.$store.getters[`${storePrefix}dashboardApplication/getFilters`]
    for (const node of root.nodes) {
      const filter = filters.find(({ id }) => String(id) === node.identifier)
      node.icon = this.app.$registry
        .get('field', filter.type || 'text')
        .getIconClass()
      if (node.type !== 'string') continue
      // Resolve saved list selectors without adding choices to the scalar explorer.
      node.getChildNode = (identifier) =>
        identifier === '*' || /^[0-9]+$/.test(identifier)
          ? {
              identifier,
              name:
                identifier === '*'
                  ? `[${this.app.$i18n.t('common.all')}]`
                  : identifier,
            }
          : null
    }
    return root
  }
}

export class DashboardTableDataProviderType extends DataProviderType {
  static getType() {
    return 'table'
  }

  isValid(path) {
    return (
      path.length >= 1 &&
      /^[1-9][0-9]*$/.test(path[0]) &&
      (path.length === 1 || path[1] === '*' || /^[0-9]+$/.test(path[1])) &&
      (path.length < 3 ||
        path[2] === 'id' ||
        /^field_[1-9][0-9]*$/.test(path[2]))
    )
  }

  get name() {
    return this.app.$i18n.t('dataProviderType.dataSource')
  }

  getDataContent() {
    // Table values are resolved by the backend when loading filter options.
    return {}
  }

  getDataChunk(context, path) {
    return getValueAtPath(this.getDataContent(context), path)
  }

  getDataSchema({ storePrefix = '' }) {
    const getters = this.app.$store.getters
    const prefix = `${storePrefix}dashboardApplication/`
    const sourceIds = new Set(
      getters[prefix + 'getWidgets'].map((widget) => widget.data_source_id)
    )
    const properties = {}
    for (const source of getters[prefix + 'getDataSources']) {
      if (
        sourceIds.has(source.id) &&
        source.table_schema &&
        !Object.hasOwn(properties, source.table_id)
      ) {
        properties[source.table_id] = {
          ...source.table_schema,
          order: Object.keys(properties).length,
        }
      }
    }
    return { type: 'object', properties }
  }
}
