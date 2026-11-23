import flushPromises from 'flush-promises'

import PromoteIntegrationModal from '@baserow/modules/core/components/integrations/PromoteIntegrationModal'
import { TestApp } from '@baserow/test/helpers/testApp'

const WORKSPACE = { id: 1, name: 'Acme' }
const DATABASE_ID = 10
const SHARED_ID = 20

const databaseApplication = {
  id: DATABASE_ID,
  type: 'database',
  name: 'Customers',
  order: 1,
  workspace: { id: WORKSPACE.id, name: WORKSPACE.name },
  tables: [],
}

const sharedApplication = {
  id: SHARED_ID,
  type: 'shared',
  name: '__shared__',
  order: 0,
  workspace: { id: WORKSPACE.id, name: WORKSPACE.name },
}

const ME = { id: 1, first_name: 'Ada', username: 'ada@example.com' }

// Authorized as another person, so promoting it authorizes it as the user.
const localBaserowIntegration = (values = {}) => ({
  id: 5,
  application_id: DATABASE_ID,
  type: 'local_baserow',
  name: 'Rows',
  order: '1',
  authorized_subject: {
    id: 2,
    type: 'auth.User',
    first_name: 'Grace',
    username: 'grace@example.com',
  },
  ...values,
})

describe('PromoteIntegrationModal', () => {
  let testApp = null
  let store = null

  beforeEach(async () => {
    testApp = new TestApp()
    store = testApp.store
    testApp.authenticate(ME)
    await store.dispatch('workspace/forceCreate', { ...WORKSPACE })
    await store.dispatch('application/forceSetAll', {
      applications: [databaseApplication, sharedApplication],
    })
    await store.dispatch('integration/forceCreate', {
      application: store.getters['application/get'](DATABASE_ID),
      integration: localBaserowIntegration(),
    })
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const get = (id) => store.getters['application/get'](id)
  const ids = (id) =>
    store.getters['integration/getIntegrations'](get(id)).map(({ id }) => id)

  // The teleported modal element is replaced on re-render, so it must be
  // fetched freshly for every assertion.
  const element = (wrapper) => wrapper.vm.getTeleportedElement()

  const openModal = async () => {
    const application = get(DATABASE_ID)
    const wrapper = await testApp.mount(PromoteIntegrationModal, {
      props: {
        application,
        integration: store.getters['integration/getIntegrationById'](
          application,
          5
        ),
      },
    })
    wrapper.vm.show()
    await flushPromises()
    return wrapper
  }

  const confirm = async (wrapper) => {
    const buttons = [...element(wrapper).querySelectorAll('button')]
    buttons[buttons.length - 1].click()
    await flushPromises()
  }

  const movedResponse = () =>
    localBaserowIntegration({
      application_id: SHARED_ID,
      order: '2',
      authorized_subject: { ...ME, type: 'auth.User' },
    })

  test('says what the promotion changes before moving anything', async () => {
    const wrapper = await openModal()

    const text = element(wrapper).textContent
    expect(text).toContain('promoteIntegration.title')
    expect(text).toContain('promoteIntegration.description')
    expect(text).toContain('promoteIntegration.keepsWorking')
    // Who it will run as in every application of the workspace.
    expect(text).toContain(
      'localBaserowIntegrationType.localBaserowPromotionReauthorizeHint'
    )
    // And what builders of other applications can then do as them.
    expect(text).toContain(
      'localBaserowIntegrationType.localBaserowPromotionAccessHint'
    )
    expect(testApp.mock.history.patch).toHaveLength(0)
  })

  test('moves the integration to the shared application once confirmed', async () => {
    testApp.mock.onPatch('integration/5/').replyOnce(200, movedResponse())
    const wrapper = await openModal()

    await confirm(wrapper)

    expect(JSON.parse(testApp.mock.history.patch[0].data)).toEqual({
      application_id: SHARED_ID,
    })
    expect(ids(DATABASE_ID)).toEqual([])
    expect(ids(SHARED_ID)).toEqual([5])
    // With the person the backend authorized it as.
    expect(
      store.getters['integration/getIntegrations'](get(SHARED_ID))[0]
        .authorized_subject.id
    ).toBe(ME.id)
    // The integration left the application's list, so the user is told where
    // it went.
    expect(store.state.toast.items).toMatchObject([
      { type: 'success', title: 'promoteIntegration.successTitle' },
    ])
  })

  test('fetches the shared application when the store does not have it', async () => {
    // Like a workspace created after the applications were loaded.
    await store.dispatch('application/forceSetAll', {
      applications: [databaseApplication],
    })
    await store.dispatch('integration/forceCreate', {
      application: get(DATABASE_ID),
      integration: localBaserowIntegration(),
    })
    testApp.mock
      .onGet(`/applications/workspace/${WORKSPACE.id}/`)
      .replyOnce(200, [databaseApplication, sharedApplication])
      .onPatch('integration/5/')
      .replyOnce(200, movedResponse())
    const wrapper = await openModal()

    await confirm(wrapper)

    expect(ids(DATABASE_ID)).toEqual([])
    expect(ids(SHARED_ID)).toEqual([5])
  })

  test('shows why a refused promotion failed and keeps the integration', async () => {
    testApp.dontFailOnErrorResponses()
    testApp.mock.onPatch('integration/5/').replyOnce(400, {
      error: 'ERROR_INTEGRATION_CANNOT_MOVE_TO_APPLICATION',
      detail: 'The integration cannot be moved to this application.',
    })
    const wrapper = await openModal()

    await confirm(wrapper)

    expect(element(wrapper).querySelector('.alert')).not.toBeNull()
    expect(ids(DATABASE_ID)).toEqual([5])
    expect(ids(SHARED_ID)).toEqual([])
    expect(store.state.toast.items).toEqual([])
  })
})
