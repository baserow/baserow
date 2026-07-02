import { TestApp } from '@baserow/test/helpers/testApp'
import GridViewGroupByBanner from '@baserow/modules/database/components/view/grid/GridViewGroupByBanner'

describe('GridViewGroupByBanner component', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountBanner = (field, { path, display }) =>
    testApp.mount(GridViewGroupByBanner, {
      props: {
        groupByFields: [field],
        item: {
          depth: 0,
          path,
          display,
          rowCount: 1,
          collapsed: false,
          y: 0,
          height: 48,
        },
        includeRowDetails: true,
        primaryFieldWidth: 200,
        width: 300,
        workspaceId: null,
      },
    })

  test('renders the collaborator name from the backend display value', async () => {
    const field = { id: 1, type: 'multiple_collaborators', name: 'People' }
    const wrapper = await mountBanner(field, {
      path: { field_1: [10] },
      display: { field_1: [{ id: 10, name: 'Davide' }] },
    })

    expect(wrapper.text()).toContain('Davide')
    // The raw collaborator id must no longer leak into the header.
    expect(wrapper.text()).not.toContain('10')
  })

  test('renders the linked row primary value from the backend display value', async () => {
    const field = { id: 2, type: 'link_row', name: 'Links' }
    const wrapper = await mountBanner(field, {
      path: { field_2: [5] },
      display: { field_2: [{ id: 5, value: 'Row A' }] },
    })

    expect(wrapper.text()).toContain('Row A')
  })

  test('renders the single select value from the backend display value', async () => {
    const field = {
      id: 3,
      type: 'single_select',
      name: 'Status',
      select_options: [],
    }
    const wrapper = await mountBanner(field, {
      path: { field_3: 7 },
      display: { field_3: { id: 7, value: 'Open', color: 'blue' } },
    })

    expect(wrapper.text()).toContain('Open')
  })

  test('renders the multiple select values from the backend display value', async () => {
    const field = {
      id: 5,
      type: 'multiple_select',
      name: 'Tags',
      select_options: [],
    }
    const wrapper = await mountBanner(field, {
      path: { field_5: [7, 8] },
      display: {
        field_5: [
          { id: 7, value: 'Red', color: 'red' },
          { id: 8, value: 'Blue', color: 'blue' },
        ],
      },
    })

    expect(wrapper.text()).toContain('Red')
    expect(wrapper.text()).toContain('Blue')
  })

  test('renders a scalar field from the path value when no display is present', async () => {
    const field = { id: 4, type: 'text', name: 'Title' }
    const wrapper = await mountBanner(field, {
      path: { field_4: 'hello world' },
      display: undefined,
    })

    expect(wrapper.text()).toContain('hello world')
  })

  test('shows the empty label for an empty array-valued group', async () => {
    const field = {
      id: 6,
      type: 'multiple_select',
      name: 'Tags',
      select_options: [],
    }
    const wrapper = await mountBanner(field, {
      path: { field_6: [] },
      display: { field_6: [] },
    })

    // An empty array (multiple select / link row / collaborators) must render the
    // empty-value label, not a blank group-value component.
    expect(
      wrapper.find('.grid-view__group-by-banner-value-empty').exists()
    ).toBe(true)
  })

  const mountAtDepth = (fieldCount, depth, rowDetailsWidth = 72) =>
    testApp.mount(GridViewGroupByBanner, {
      props: {
        groupByFields: Array.from({ length: fieldCount }, (_, i) => ({
          id: i + 1,
          type: 'text',
          name: `Field ${i + 1}`,
        })),
        item: {
          depth,
          path: { [`field_${depth + 1}`]: 'x' },
          display: undefined,
          rowCount: 1,
          collapsed: false,
          y: 0,
          height: 48,
        },
        includeRowDetails: true,
        primaryFieldWidth: 200,
        rowDetailsWidth,
        width: 300,
        workspaceId: null,
      },
    })

  const chevronPadding = (wrapper) =>
    parseFloat(
      wrapper.find('.grid-view__group-by-banner-chevron-lane').element.style
        .paddingLeft
    )

  test('caps the chevron indent so deep nesting stops shifting right', async () => {
    // 14 levels: the deepest chevron must still fit inside the 72px row-details lane
    // (base 12 + at most 36 = 48, leaving room for the 24px chevron) so it never
    // marches the field name + count off to the right.
    const deepest = await mountAtDepth(14, 13)
    const pad = chevronPadding(deepest)
    expect(pad).toBeGreaterThan(12)
    expect(pad).toBeLessThanOrEqual(48)
  })

  test('shrinks the per-level step as the number of group-bys grows', async () => {
    const fewStep = chevronPadding(await mountAtDepth(3, 1)) - 12
    const manyStep = chevronPadding(await mountAtDepth(13, 1)) - 12
    expect(manyStep).toBeLessThan(fewStep)
    expect(manyStep).toBeGreaterThan(0)
  })

  test('indents the field-name block in lockstep with its chevron', async () => {
    const subGroup = await mountAtDepth(2, 1)
    const labelPadding = parseFloat(
      subGroup.find('.grid-view__group-by-banner-primary').element.style
        .paddingLeft
    )
    expect(labelPadding).toBe(chevronPadding(subGroup))
    expect(labelPadding).toBeGreaterThan(12)
  })
})
