import { TestApp } from '@baserow/test/helpers/testApp'
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

    expect(wrapper.text()).toBe('snapshotModalWarning.messageDatabase')
  })

  test.each(['automation', 'builder', 'dashboard'])(
    'only mentions the application itself for %s',
    async (type) => {
      const wrapper = await mountFor(type)

      expect(wrapper.text()).toBe('snapshotModalWarning.messageApplication')
    }
  )
})
