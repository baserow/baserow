import { DataSourcesPageHeaderItemType } from '@baserow/modules/builder/pageHeaderItemTypes'
import { LocalBaserowGetRowServiceType } from '@baserow/modules/integrations/localBaserow/serviceTypes'

// Builds a fake app whose service registry returns a real
// `LocalBaserowGetRowServiceType`, so the header's `isInError` is exercised end to
// end (header -> serviceType.isInError -> getErrorMessage -> integration lookup).
const buildHeaderItemType = ({ dataSources, integrations }) => {
  const fakeApp = {
    $i18n: { t: (key) => key },
    $store: {
      getters: {
        'page/getSharedPage': () => ({ id: 99 }),
        'dataSource/getPagesDataSources': () => dataSources,
        'integration/getIntegrationById': (application, id) => integrations[id],
      },
    },
  }
  const serviceType = new LocalBaserowGetRowServiceType({ app: fakeApp })
  fakeApp.$registry = { get: () => serviceType }
  return new DataSourcesPageHeaderItemType({ app: fakeApp })
}

describe('DataSourcesPageHeaderItemType.isInError', () => {
  const builder = { id: 1 }
  const page = { id: 2 }

  test('flags an error when a data source integration has been trashed', () => {
    // Integration 41 is not in the store (trashed), so it can't be resolved.
    const headerItemType = buildHeaderItemType({
      dataSources: [
        { id: 1, type: 'local_baserow_get_row', integration_id: 41, table_id: 99 },
      ],
      integrations: {},
    })

    expect(headerItemType.isInError({ builder, page })).toBe(true)
  })

  test('is not in error when the integration resolves', () => {
    const headerItemType = buildHeaderItemType({
      dataSources: [
        { id: 1, type: 'local_baserow_get_row', integration_id: 5, table_id: 99 },
      ],
      integrations: { 5: { id: 5, type: 'local_baserow' } },
    })

    expect(headerItemType.isInError({ builder, page })).toBe(false)
  })
})
