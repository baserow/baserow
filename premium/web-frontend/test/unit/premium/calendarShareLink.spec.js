import { PremiumTestApp } from '@baserow_premium_test/helpers/premiumTestApp'
import MockPremiumServer from '@baserow_premium_test/fixtures/mockPremiumServer'
import ShareViewLink from '@baserow/modules/database/components/view/ShareViewLink'
import Context from '@baserow/modules/core/components/Context'
import flushPromises from 'flush-promises'
import ViewRotateSlugModal from '@baserow/modules/database/components/view/ViewRotateSlugModal.vue'

async function openShareViewLinkContext(testApp, view) {
  const shareViewLinkComponent = await testApp.mount(ShareViewLink, {
    props: {
      view,
      readOnly: false,
    },
  })
  // open share view
  await shareViewLinkComponent.find('.header__filter-link').trigger('click')
  // find context container
  const context = shareViewLinkComponent.findComponent(Context)
  // which should be visible
  expect(context.isVisible()).toBe(true)
  return shareViewLinkComponent
}

describe('Premium Share View Calendar ical feed Tests', () => {
  let testApp = null
  let mockServer = null

  beforeEach(() => {
    testApp = new PremiumTestApp()
    mockServer = new MockPremiumServer(testApp.mock)
  })

  afterEach(async () => await testApp.afterEach())

  // TODO MIG skipped
  test.skip('User with global premium can share ical feed url', async () => {
    const workspace = { id: 1, name: 'testWorkspace' }
    await testApp.getStore().dispatch('workspace/forceCreate', workspace)

    const tableId = 1
    const databaseId = 3
    const viewId = 5

    testApp.getStore().dispatch('application/forceCreate', {
      id: databaseId,
      type: 'database',
      tables: [{ id: tableId }],
      workspace,
    })

    const icalFeedUrl = '/aaaaAAAA.ics'
    const view = {
      id: viewId,
      type: 'calendar',
      public: false,
      table: { database_id: databaseId },
      show_logo: true,
      isShared: false,
      ical_feed_url: icalFeedUrl,
      ical_public: false,
    }

    testApp.getStore().dispatch('view/forceCreate', { data: view })
    testApp.giveCurrentUserGlobalPremiumFeatures()

    const updatedView = {}
    Object.assign(updatedView, view, {
      ical_public: true,
      isShared: true,
    })
    mockServer.expectCalendarViewUpdate(viewId, updatedView)
    const shareViewLinkContext = await openShareViewLinkContext(testApp, view)

    expect(shareViewLinkContext.props('view').type).toEqual('calendar')
    expect(shareViewLinkContext.props('view').id).toEqual(viewId)
    // initial state: no shared links yet, two buttons to enable sharing
    expect(
      shareViewLinkContext.findAllComponents({ name: 'Button' })
    ).toHaveLength(2)

    // ..including: one with sync with external calendar
    expect(
      shareViewLinkContext.findAllComponents({ name: 'Button' }).at(1).text()
    ).toContain('calendarViewType.sharedViewEnableSyncToExternalCalendar')

    // sanity check: no footer links yet
    expect(
      shareViewLinkContext.findAll('.view-sharing__shared-link-foot')
    ).toHaveLength(0)

    expect(
      shareViewLinkContext.findAllComponents({ name: 'Button' })
    ).toHaveLength(2)

    // last .view-sharing__create-link is an element which needs to be clicked
    await shareViewLinkContext
      .findAllComponents({ name: 'Button' })
      .at(1)
      .trigger('click')

    // need to wait for async store stuff
    await flushPromises()

    // state changed: one shared-link element with ical_feed_url
    expect(shareViewLinkContext.props('view').ical_feed_url).toEqual(
      icalFeedUrl
    )
    expect(shareViewLinkContext.props('view').isShared).toEqual(true)
    expect(shareViewLinkContext.props('view').public).toEqual(false)

    // no create link big buttons
    expect(
      shareViewLinkContext.findAllComponents({ name: 'Button' })
    ).toHaveLength(0)

    // but two buttons in the footer, one to disable the sync
    expect(
      shareViewLinkContext
        .findAllComponents({ name: 'ButtonText' })
        .at(1)
        .text()
    ).toContain('calendarViewType.sharedViewDisableSyncToExternalCalendar')

    // one shared link option for calendar ical feed
    expect(
      shareViewLinkContext
        .findAll('.view-sharing__shared-link')
        .filter((el) =>
          el.text().includes('calendarViewType.sharedViewDescription')
        )
    ).toHaveLength(1)
  })

  // TODO MIG skipped
  test.skip('User with global premium can rotate ical feed slug', async () => {
    const workspace = { id: 1, name: 'testWorkspace' }
    await testApp.getStore().dispatch('workspace/forceCreate', workspace)
    const tableId = 1
    const databaseId = 3
    const viewId = 5
    testApp.getStore().dispatch('application/forceCreate', {
      id: databaseId,
      type: 'database',
      tables: [{ id: tableId }],
      workspace,
    })
    const icalFeedUrl = '/aaaaAAAA.ics'
    const icalFeedRotatedUrl = '/bbbbBBBB.ics'
    const view = {
      id: viewId,
      type: 'calendar',
      public: false,
      table: { database_id: databaseId },
      show_logo: true,
      isShared: false,
      ical_feed_url: icalFeedUrl,
      ical_public: false,
    }

    testApp.getStore().dispatch('view/forceCreate', { data: view })
    testApp.giveCurrentUserGlobalPremiumFeatures()

    const publicView = {}
    Object.assign(publicView, view, {
      // ical_feed_url: icalFeedUrl,
      isShared: true,
      ical_public: true,
    })

    const rotatedSlugView = {}
    Object.assign(rotatedSlugView, view, {
      ical_feed_url: icalFeedRotatedUrl,
      isShared: true,
      ical_public: true,
    })

    mockServer.expectCalendarViewUpdate(viewId, publicView)
    mockServer.expectCalendarRefreshShareURLUpdate(viewId, rotatedSlugView)

    const shareViewLinkContext = await openShareViewLinkContext(testApp, view)

    // sanity checks
    expect(shareViewLinkContext.props('view').type).toEqual('calendar')
    expect(shareViewLinkContext.props('view').id).toEqual(viewId)

    expect(
      shareViewLinkContext.findAllComponents({ name: 'Button' })
    ).toHaveLength(2)

    // ..including: one with sync with external calendar
    expect(
      shareViewLinkContext
        .findAllComponents({ name: 'Button' })
        .filter((el) =>
          el
            .text()
            .includes('calendarViewType.sharedViewEnableSyncToExternalCalendar')
        )
    ).toHaveLength(1)

    // last .view-sharing__create-link is an element which needs to be clicked
    await shareViewLinkContext
      .findAllComponents({ name: 'Button' })
      .at(1)
      .trigger('click')

    // need to wait for async store stuff
    await flushPromises()
    // state changed: one shared-link element with ical_feed_url

    expect(shareViewLinkContext.props('view').ical_feed_url).toEqual(
      icalFeedUrl
    )
    expect(shareViewLinkContext.props('view').isShared).toEqual(true)
    expect(shareViewLinkContext.props('view').public).toEqual(false)

    // check for rotate slug component
    expect(
      shareViewLinkContext
        .findComponent({ name: 'ViewRotateSlugModal' })
        .exists()
    ).toBe(true)

    // it should be the last one out of two
    expect(
      shareViewLinkContext.findAll('.view-sharing__shared-link-action')
    ).toHaveLength(2)

    // refresh slug click..
    await shareViewLinkContext
      .findAll('.view-sharing__shared-link-action')
      .at(1)
      .trigger('click')
    // ..but this opens a modal with a button!
    expect(
      shareViewLinkContext
        .findComponent(ViewRotateSlugModal)
        .findAll('.actions button')
    ).toHaveLength(1)
    // which has a button to click
    shareViewLinkContext
      .findComponent(ViewRotateSlugModal)
      .findAll('.actions button')
      .at(0)
      .trigger('click')

    await flushPromises()
    await shareViewLinkContext.vm.$nextTick()

    expect(shareViewLinkContext.props('view').ical_feed_url).toEqual(
      icalFeedRotatedUrl
    )
  })
})
