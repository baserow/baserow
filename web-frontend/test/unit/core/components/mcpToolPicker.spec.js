import { TestApp } from '@baserow/test/helpers/testApp'
import McpToolPicker from '@baserow/modules/core/components/mcp/McpToolPicker.vue'

describe('McpToolPicker', () => {
  let testApp = null

  const groups = [
    {
      type: 'database_read',
      title: 'Read databases',
      area: 'database',
      read_only_preset: true,
    },
    {
      type: 'database_edit',
      title: 'Edit databases',
      area: 'database',
      read_only_preset: false,
    },
    {
      type: 'database_delete',
      title: 'Delete in databases',
      area: 'database',
      read_only_preset: false,
    },
    {
      type: 'builder_read',
      title: 'Read applications',
      area: 'builder',
      read_only_preset: true,
    },
  ]
  const tools = [
    {
      name: 'list_tables',
      title: 'List tables',
      read_only: true,
      destructive: false,
      group: 'database_read',
    },
    {
      name: 'create_rows',
      title: 'Create rows',
      read_only: false,
      destructive: false,
      group: 'database_edit',
    },
    {
      name: 'update_rows',
      title: 'Update rows',
      read_only: false,
      destructive: true,
      group: 'database_edit',
    },
    {
      name: 'delete_rows',
      title: 'Delete rows',
      read_only: false,
      destructive: true,
      group: 'database_delete',
    },
    {
      name: 'list_pages',
      title: 'List pages',
      read_only: true,
      destructive: false,
      group: 'builder_read',
    },
  ]
  const allTools = tools.map((tool) => tool.name)

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  async function mount(props = {}) {
    let selected = props.modelValue ?? []
    const wrapper = await testApp.mount(McpToolPicker, {
      props: {
        tools,
        groups,
        modelValue: selected,
        'onUpdate:modelValue': async (value) => {
          selected = value
          await wrapper.setProps({ modelValue: value })
        },
        ...props,
      },
    })
    return { wrapper, selected: () => selected }
  }

  function toolCheckbox(wrapper, name) {
    return wrapper.find(`[data-test="mcp-tool-picker-tool-${name}"] input`)
  }

  function ticked(wrapper) {
    return allTools.filter(
      (name) =>
        toolCheckbox(wrapper, name).exists() &&
        toolCheckbox(wrapper, name).element.checked
    )
  }

  test('lists every tool under its group, groups under their area', async () => {
    const { wrapper } = await mount()
    const area = (key) =>
      wrapper.find(`[data-test="mcp-tool-picker-area-${key}"]`)
    const group = (key) =>
      wrapper.find(`[data-test="mcp-tool-picker-group-${key}"]`)
    expect(area('database').text()).toContain('List tables')
    expect(area('database').text()).not.toContain('List pages')
    expect(area('builder').text()).toContain('List pages')
    expect(group('database_edit').text()).toContain('Create rows')
    expect(group('database_edit').text()).toContain('Update rows')
    expect(group('database_edit').text()).not.toContain('Delete rows')
  })

  test('labels the automation groups and area', async () => {
    const automationGroups = [
      {
        type: 'automation_read',
        title: 'Read automations',
        area: 'automation',
        read_only_preset: false,
      },
      {
        type: 'automation_edit',
        title: 'Edit automations',
        area: 'automation',
        read_only_preset: false,
      },
      {
        type: 'automation_delete',
        title: 'Delete in automations',
        area: 'automation',
        read_only_preset: false,
      },
    ]
    const automationTools = [
      ['list_workflows', 'automation_read'],
      ['create_workflows', 'automation_edit'],
      ['delete_nodes', 'automation_delete'],
    ].map(([name, group]) => ({
      name,
      title: name,
      read_only: group === 'automation_read',
      destructive: group === 'automation_delete',
      group,
    }))
    const { wrapper } = await mount({
      groups: automationGroups,
      tools: automationTools,
    })
    const area = wrapper.find('[data-test="mcp-tool-picker-area-automation"]')
    const group = (key) =>
      wrapper.find(`[data-test="mcp-tool-picker-group-${key}"]`)
    // The test app renders translation keys: the labels are translated, not
    // the API's fallback titles.
    expect(area.text()).toContain('mcpToolPicker.areaAutomation')
    expect(group('automation_read').text()).toContain(
      'mcpToolPicker.automationRead'
    )
    expect(group('automation_edit').text()).toContain(
      'mcpToolPicker.automationEdit'
    )
    expect(group('automation_delete').text()).toContain(
      'mcpToolPicker.automationDelete'
    )
    expect(area.text()).not.toContain('Read automations')
  })

  test('shows the ticked tools from the model value', async () => {
    const { wrapper } = await mount({ modelValue: ['create_rows'] })
    expect(ticked(wrapper)).toEqual(['create_rows'])
  })

  test('the read only preset ticks the read groups, nothing destructive', async () => {
    const { wrapper, selected } = await mount({ modelValue: allTools })
    await wrapper
      .find('[data-test="mcp-tool-picker-read-only"]')
      .trigger('click')
    expect(selected()).toEqual(['list_tables', 'list_pages'])
    expect(ticked(wrapper)).toEqual(['list_tables', 'list_pages'])
  })

  test('the read only preset skips a destructive tool in a read group', async () => {
    const { wrapper, selected } = await mount({
      tools: [
        ...tools,
        {
          name: 'odd_tool',
          title: 'Odd',
          read_only: false,
          destructive: true,
          group: 'database_read',
        },
      ],
    })
    await wrapper
      .find('[data-test="mcp-tool-picker-read-only"]')
      .trigger('click')
    expect(selected()).toEqual(['list_tables', 'list_pages'])
  })

  test('full access ticks every tool and none unticks them', async () => {
    const { wrapper, selected } = await mount()
    await wrapper
      .find('[data-test="mcp-tool-picker-full-access"]')
      .trigger('click')
    expect(selected()).toEqual(allTools)
    await wrapper.find('[data-test="mcp-tool-picker-none"]').trigger('click')
    expect(selected()).toEqual([])
  })

  test('the preset links are keyboard reachable buttons', async () => {
    const { wrapper } = await mount()
    for (const key of ['read-only', 'full-access', 'none']) {
      const button = wrapper.find(`[data-test="mcp-tool-picker-${key}"]`)
      expect(button.element.tagName).toBe('BUTTON')
      expect(button.attributes('type')).toBe('button')
    }
  })

  test('ticking a tool adds it in the listed order', async () => {
    const { wrapper, selected } = await mount({ modelValue: ['list_pages'] })
    await toolCheckbox(wrapper, 'create_rows').setValue(true)
    expect(selected()).toEqual(['create_rows', 'list_pages'])
    await toolCheckbox(wrapper, 'list_pages').setValue(false)
    expect(selected()).toEqual(['create_rows'])
  })

  test('the group checkbox ticks and unticks its whole group', async () => {
    const { wrapper, selected } = await mount({ modelValue: ['create_rows'] })
    const groupBox = wrapper.find(
      '[data-test="mcp-tool-picker-group-toggle-database_edit"]'
    )
    expect(groupBox.find('[aria-checked="mixed"]').exists()).toBe(true)
    await groupBox.find('input').setValue(true)
    expect(selected()).toEqual(['create_rows', 'update_rows'])
    await groupBox.find('input').setValue(false)
    expect(selected()).toEqual([])
  })

  test('destructive tools get a Deletes or Overwrites badge', async () => {
    const { wrapper } = await mount()
    const badge = (name) =>
      wrapper.find(`[data-test="mcp-tool-picker-badge-${name}"]`)
    expect(badge('delete_rows').text()).toBe('mcpToolPicker.deletes')
    expect(badge('delete_rows').classes()).toContain('badge--red')
    expect(badge('update_rows').text()).toBe('mcpToolPicker.overwrites')
    expect(badge('update_rows').classes()).toContain('badge--yellow')
    expect(badge('create_rows').exists()).toBe(false)
  })

  test('a group without a translation shows its API title', async () => {
    const { wrapper } = await mount({
      groups: [
        ...groups,
        { type: 'other', title: 'Other things', area: 'other' },
      ],
      tools: [
        ...tools,
        {
          name: 'other_tool',
          title: 'Other tool',
          read_only: true,
          destructive: false,
          group: 'other',
        },
      ],
    })
    expect(
      wrapper.find('[data-test="mcp-tool-picker-group-other"]').text()
    ).toContain('Other things')
  })

  test('a tool outside the listed groups is never shown or picked', async () => {
    const { wrapper, selected } = await mount({
      tools: [
        ...tools,
        {
          name: 'stray_tool',
          title: 'Stray',
          read_only: true,
          destructive: false,
          group: 'unknown',
        },
      ],
    })
    expect(toolCheckbox(wrapper, 'stray_tool').exists()).toBe(false)
    await wrapper
      .find('[data-test="mcp-tool-picker-full-access"]')
      .trigger('click')
    expect(selected()).toEqual(allTools)
  })

  test('the read only preset skips a write tool in a read group', async () => {
    const { wrapper, selected } = await mount({
      tools: [
        ...tools,
        {
          name: 'quiet_write',
          title: 'Quiet write',
          read_only: false,
          destructive: false,
          group: 'database_read',
        },
      ],
    })
    await wrapper
      .find('[data-test="mcp-tool-picker-read-only"]')
      .trigger('click')
    expect(selected()).toEqual(['list_tables', 'list_pages'])
  })

  test('a destructive tool in a delete group gets the Deletes badge', async () => {
    const { wrapper } = await mount({
      tools: [
        ...tools,
        {
          name: 'remove_rows',
          title: 'Remove rows',
          read_only: false,
          destructive: true,
          group: 'database_delete',
        },
      ],
    })
    expect(
      wrapper.find('[data-test="mcp-tool-picker-badge-remove_rows"]').text()
    ).toBe('mcpToolPicker.deletes')
  })

  test('an area without a translation shows its key', async () => {
    const { wrapper } = await mount({
      groups: [...groups, { type: 'other', title: 'Other', area: 'extras' }],
      tools: [
        ...tools,
        {
          name: 'other_tool',
          title: 'Other tool',
          read_only: true,
          destructive: false,
          group: 'other',
        },
      ],
    })
    expect(
      wrapper.find('[data-test="mcp-tool-picker-area-extras"]').text()
    ).toContain('extras')
  })
})
