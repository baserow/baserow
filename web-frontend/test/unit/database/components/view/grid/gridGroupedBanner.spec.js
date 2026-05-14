/**
 * Structural tests for the Airtable-style group banner. The visual
 * polish (exact pixel values, hover, transitions) is covered by e2e
 * snapshots; here we assert the banner has the right *parts* and
 * obeys the depth-indent contract.
 */
import { TestApp } from '@baserow/test/helpers/testApp'
import GridGroupedBanner from '@baserow/modules/database/components/view/grid/GridGroupedBanner'

describe('GridGroupedBanner', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountBanner = async (overrides = {}) => {
    const item = {
      type: 'header',
      depth: 0,
      path: { field_1: 'Development' },
      rowCount: 7,
      y: 100,
      height: 48,
      collapsed: false,
      ...overrides.item,
    }
    const groupByFields = overrides.groupByFields ?? [
      { id: 1, name: 'Category', type: 'text' },
    ]
    return testApp.mount(GridGroupedBanner, {
      props: { item, groupByFields },
    })
  }

  test('renders the field-name label uppercased', async () => {
    const wrapper = await mountBanner({
      groupByFields: [{ id: 1, name: 'Category', type: 'text' }],
    })
    expect(wrapper.find('.grid-grouped-banner__label').text()).toBe('CATEGORY')
  })

  test('renders the row count', async () => {
    const wrapper = await mountBanner({ item: { rowCount: 4832 } })
    expect(wrapper.find('.grid-grouped-banner__count').text()).toBe('4832')
  })

  test('depth-0 banner has a 12px base gutter; deeper banners add 24px per level', async () => {
    // The indent lives on the chevron lane — depth-0 banners sit at
    // the base gutter (matching the row-id column's left padding so
    // the chevron aligns with the row number underneath), deeper
    // banners push the chevron right so nested groups read as
    // visually nested under their parent.
    const chevronOf = (w) =>
      w.find('.grid-grouped-banner__chevron-lane').element

    const d0 = await mountBanner({ item: { depth: 0 } })
    expect(chevronOf(d0).style.paddingLeft).toBe('12px')

    const d1 = await mountBanner({ item: { depth: 1 } })
    expect(chevronOf(d1).style.paddingLeft).toBe('36px')

    const d2 = await mountBanner({ item: { depth: 2 } })
    expect(chevronOf(d2).style.paddingLeft).toBe('60px')
  })

  test('y / height are written through to position the banner absolutely', async () => {
    const wrapper = await mountBanner({ item: { y: 696, height: 48 } })
    expect(wrapper.element.style.top).toBe('696px')
    expect(wrapper.element.style.height).toBe('48px')
  })

  test('collapsed banner exposes the state via data-attribute + class', async () => {
    const wrapper = await mountBanner({ item: { collapsed: true } })
    expect(wrapper.attributes('data-collapsed')).toBe('true')
    expect(wrapper.classes()).toContain('grid-grouped-banner--collapsed')
  })

  test('clicking the chevron emits a toggle event with the path', async () => {
    const path = { field_1: 'Development', field_2: true }
    const wrapper = await mountBanner({ item: { path, depth: 1 } })
    await wrapper.find('.grid-grouped-banner__toggle').trigger('click')
    expect(wrapper.emitted('toggle')).toBeDefined()
    expect(wrapper.emitted('toggle')[0][0]).toEqual(path)
  })

  test('null group value renders as "(Empty)" italic, not as the empty string', async () => {
    const wrapper = await mountBanner({
      item: { path: { field_1: null } },
    })
    const empty = wrapper.find('.grid-grouped-banner__value-empty')
    expect(empty.exists()).toBe(true)
    expect(empty.text()).toBe('(Empty)')
  })

  test('text-typed group value renders without an empty placeholder', async () => {
    const wrapper = await mountBanner({
      item: { path: { field_1: 'Development' } },
    })
    expect(wrapper.find('.grid-grouped-banner__value-empty').exists()).toBe(
      false
    )
  })

  test('chevron icon flips between right (collapsed) and down (expanded)', async () => {
    const collapsed = await mountBanner({ item: { collapsed: true } })
    expect(
      collapsed.find('.grid-grouped-banner__toggle i').classes()
    ).toContain('iconoir-nav-arrow-right')

    const expanded = await mountBanner({ item: { collapsed: false } })
    expect(expanded.find('.grid-grouped-banner__toggle i').classes()).toContain(
      'iconoir-nav-arrow-down'
    )
  })
})
