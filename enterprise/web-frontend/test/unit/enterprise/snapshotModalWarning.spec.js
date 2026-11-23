import { TestApp } from '@baserow/test/helpers/testApp'
import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'
import SnapshotModalWarning from '@baserow_enterprise/components/SnapshotModalWarning'

describe('SnapshotModalWarning', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountFor = (type) =>
    testApp.mount(SnapshotModalWarning, {
      props: { application: { id: 1, type, workspace: { id: 1 } } },
    })

  test('mentions the tables and views of a database', async () => {
    const wrapper = await mountFor('database')

    expect(wrapper.text()).toBe('databaseSnapshotPermissions.description')
  })

  test.each(['automation', 'builder', 'dashboard'])(
    'only mentions the application itself for %s',
    async (type) => {
      const wrapper = await mountFor(type)

      expect(wrapper.text()).toBe('applicationSnapshotPermissions.description')
    }
  )

  test('uses the permission description provided by a custom application type', async () => {
    class CustomApplicationType extends DatabaseApplicationType {
      static getType() {
        return 'custom_snapshot_application'
      }

      getSnapshotPermissionDescription() {
        return 'customSnapshotPermissions.description'
      }
    }

    testApp.$registry.register(
      'application',
      new CustomApplicationType({ app: testApp.nuxtApp })
    )
    try {
      const wrapper = await mountFor('custom_snapshot_application')
      expect(wrapper.text()).toBe('customSnapshotPermissions.description')
    } finally {
      testApp.$registry.unregister('application', 'custom_snapshot_application')
    }
  })
})
