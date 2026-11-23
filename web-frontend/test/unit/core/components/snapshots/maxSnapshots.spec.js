import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import MaxSnapshots from '@baserow/modules/core/components/snapshots/MaxSnapshots'

describe('MaxSnapshots', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const usage = (values = {}) => ({
    used: 4,
    limit: 5,
    over_allowance: false,
    snapshot_count: 2,
    default_max_snapshots: 2,
    max_snapshots_limit: null,
    expiration_days: 360,
    max_snapshots: null,
    effective_max_snapshots: 2,
    application_snapshot_count: 2,
    protected_count: 0,
    ...values,
  })

  const snapshots = [
    {
      id: 2,
      name: 'Newest',
      created_at: '2026-11-02T10:00:00Z',
      protected: false,
    },
    {
      id: 1,
      name: 'Oldest',
      created_at: '2026-11-01T10:00:00Z',
      protected: false,
    },
  ]

  const mountComponent = (values = {}) =>
    testApp.mount(MaxSnapshots, {
      props: {
        application: { id: 7, name: 'CRM' },
        usage: usage(values),
        snapshots,
        canUpdate: true,
      },
    })

  const findButton = (wrapper, text) =>
    wrapper.findAll('button').find((button) => button.text() === text)

  test('says the max snapshots comes from the workspace default', async () => {
    const wrapper = await mountComponent()

    expect(wrapper.find('.max-snapshots__value').text()).toBe('2')
    expect(wrapper.text()).toContain('maxSnapshots.descriptionDefault')
  })

  test.each([
    [null, 0, 0, 'maxSnapshots.sourceWorkspace - 0'],
    [null, 2, 2, 'maxSnapshots.sourceWorkspace - 2'],
    [0, 0, 2, null],
    [2, 2, 2, null],
  ])(
    'shows the saved source for maximum %s, effective %s and default %s',
    async (maximum, effective, workspaceDefault, label) => {
      const wrapper = await mountComponent({
        max_snapshots: maximum,
        effective_max_snapshots: effective,
        default_max_snapshots: workspaceDefault,
      })

      const source = wrapper.find('.max-snapshots__source')
      expect(source.exists()).toBe(label !== null)
      if (label !== null) {
        expect(source.text()).toBe(label)
      }
      expect(wrapper.find('.max-snapshots__source--inherited').exists()).toBe(
        maximum === null
      )
      expect(wrapper.find('form').exists()).toBe(false)
    }
  )

  test('shows a validation error instead of going past the allowance', async () => {
    const wrapper = await mountComponent()

    await wrapper.vm.edit(4)
    await flushPromises()

    // Up to 3: what's left of the allowance on top of its max snapshots of 2.
    expect(wrapper.find('.max-snapshots__error').text()).toBe(
      'maxSnapshots.errorExceedsAllowance - 3'
    )
    expect(testApp.mock.history.patch).toHaveLength(0)
  })

  test('says why the workspace default cannot be used', async () => {
    const wrapper = await mountComponent({
      max_snapshots: 3,
      effective_max_snapshots: 3,
      default_max_snapshots: 0,
      used: 3,
      protected_count: 2,
    })

    await wrapper.vm.edit()
    await flushPromises()
    expect(wrapper.find('.max-snapshots__error').exists()).toBe(false)

    await wrapper
      .findAll('button')
      .find((button) => button.text().startsWith('maxSnapshots.useDefault'))
      .trigger('click')
    await flushPromises()

    expect(wrapper.find('.max-snapshots__error').text()).toBe(
      'maxSnapshots.errorBelowProtected - 2'
    )
    expect(testApp.mock.history.patch).toHaveLength(0)
  })

  test('warns when the max snapshots can go past the allowance', async () => {
    testApp.mock
      .onPatch('/snapshots/application/7/max-snapshots/')
      .reply(
        200,
        usage({ max_snapshots: 4, effective_max_snapshots: 4, used: 6 })
      )
    const wrapper = await mountComponent({ can_exceed_allowance: true })

    await wrapper.vm.edit(4)
    await flushPromises()

    expect(wrapper.find('.max-snapshots__error').exists()).toBe(false)
    expect(wrapper.find('.max-snapshots__warning').text()).toContain(
      'maxSnapshots.overAllowance'
    )
    // The max snapshots limit is the only limit left, and there's none.
    expect(wrapper.find('.max-snapshots__hint').exists()).toBe(false)

    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(JSON.parse(testApp.mock.history.patch[0].data)).toEqual({
      max_snapshots: 4,
      delete_snapshots: false,
    })
  })

  test('saves a max within the allowance', async () => {
    testApp.mock
      .onPatch('/snapshots/application/7/max-snapshots/')
      .reply(
        200,
        usage({ max_snapshots: 3, effective_max_snapshots: 3, used: 5 })
      )
    const wrapper = await mountComponent()

    await wrapper.vm.edit(3)
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(JSON.parse(testApp.mock.history.patch[0].data)).toEqual({
      max_snapshots: 3,
      delete_snapshots: false,
    })
    expect(wrapper.emitted('updated')[0][0].effective_max_snapshots).toBe(3)
  })

  test('asks before a lower max snapshots deletes snapshots', async () => {
    testApp.mock
      .onPatch('/snapshots/application/7/max-snapshots/')
      .reply(
        200,
        usage({ max_snapshots: 1, effective_max_snapshots: 1, used: 3 })
      )
    const wrapper = await mountComponent()

    await wrapper.vm.edit(1)
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('.max-snapshots__confirm').text()).toContain(
      'maxSnapshots.confirmDelete'
    )
    expect(testApp.mock.history.patch).toHaveLength(0)

    await findButton(wrapper, 'maxSnapshots.deleteAndSave').trigger('click')
    await flushPromises()

    expect(JSON.parse(testApp.mock.history.patch[0].data)).toEqual({
      max_snapshots: 1,
      delete_snapshots: true,
    })
  })
})

describe('MaxSnapshots with an out of date list', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('asks to confirm when the server says snapshots would be deleted', async () => {
    testApp.mock.onPatch('/snapshots/application/7/max-snapshots/').reply(400, {
      error: 'ERROR_MAX_SNAPSHOTS_CHANGE_DELETES_SNAPSHOTS',
      detail:
        'Lowering the max snapshots deletes 2 snapshot(s). Send `delete_snapshots`.',
    })
    const wrapper = await testApp.mount(MaxSnapshots, {
      props: {
        application: { id: 7, name: 'CRM' },
        usage: {
          used: 3,
          limit: 10,
          over_allowance: false,
          blocked: false,
          snapshot_count: 0,
          default_max_snapshots: 0,
          max_snapshots_limit: null,
          expiration_days: 360,
          max_snapshots: 3,
          effective_max_snapshots: 3,
          application_snapshot_count: 0,
          protected_count: 0,
        },
        // The list doesn't know about the snapshots that were added since.
        snapshots: [],
        canUpdate: true,
      },
    })

    await wrapper.vm.edit(1)
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.emitted('stale')).toHaveLength(1)
    expect(wrapper.find('.max-snapshots__confirm').text()).toContain(
      'maxSnapshots.confirmDelete'
    )
  })
})
