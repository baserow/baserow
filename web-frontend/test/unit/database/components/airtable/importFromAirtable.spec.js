import { TestApp } from '@baserow/test/helpers/testApp'
import ImportFromAirtable from '@baserow/modules/database/components/airtable/ImportFromAirtable'

describe('ImportFromAirtable', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const workspace = { id: 1, name: 'Workspace' }

  const airtableUrl = 'https://airtable.com/shrTestTestTestTe'

  const mountWithFailedJob = async (job) => {
    const wrapper = await testApp.mount(ImportFromAirtable, {
      propsData: { workspace },
    })
    wrapper.vm.lastAirtableUrl = airtableUrl
    wrapper.vm.job = job
    wrapper.vm.onJobFailed()
    await wrapper.vm.$nextTick()
    return wrapper
  }

  test('shows authentication guidance and expands the session section', async () => {
    const wrapper = await mountWithFailedJob({
      state: 'failed',
      error_code: 'AirtableBaseRequiresAuthentication',
      human_readable_error: 'The Airtable base requires authentication.',
    })

    expect(wrapper.html()).toContain(
      'importFromAirtable.errorRequiresAuthenticationTitle'
    )
    expect(wrapper.html()).toContain(
      'importFromAirtable.errorRequiresAuthenticationDescription'
    )
    // The session authentication section must be expanded so that the user sees
    // the instructions the error refers to.
    expect(wrapper.html()).toContain('importFromAirtable.sessionDescription')
    expect(wrapper.html()).not.toContain('importFromAirtable.openSharedLink')
  })

  test('shows not public guidance without expanding the session section', async () => {
    const wrapper = await mountWithFailedJob({
      state: 'failed',
      error_code: 'AirtableBaseNotPublic',
      human_readable_error: 'The Airtable base is not public.',
    })

    expect(wrapper.html()).toContain(
      'importFromAirtable.errorBaseNotPublicTitle'
    )
    expect(wrapper.html()).toContain(
      'importFromAirtable.errorBaseNotPublicDescription'
    )
    expect(wrapper.html()).not.toContain(
      'importFromAirtable.sessionDescription'
    )
    const openLink = wrapper.find(`a[href="${airtableUrl}"]`)
    expect(openLink.exists()).toBe(true)
    expect(openLink.text()).toBe('importFromAirtable.openSharedLink')
  })

  test('falls back to the human readable error for unmapped codes', async () => {
    const wrapper = await mountWithFailedJob({
      state: 'failed',
      error_code: '',
      human_readable_error: 'Something specific went wrong.',
    })

    expect(wrapper.html()).toContain('importFromAirtable.importError')
    expect(wrapper.html()).toContain('Something specific went wrong.')
  })
})
