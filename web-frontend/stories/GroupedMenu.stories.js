import { expect, fn } from 'storybook/test'

import GroupedMenu from '@baserow/modules/core/components/GroupedMenu'

import { groupedDropdownItems } from './menuListFixtures'

const renderMenu = (args) => ({
  components: { GroupedMenu },
  setup() {
    return { args }
  },
  template: `
    <GroupedMenu v-bind="args" />
  `,
})

export default {
  title: 'Baserow/Menus/GroupedMenu',
  component: GroupedMenu,
  tags: ['autodocs'],
  decorators: [
    () => ({
      template:
        '<div style="width: 532px; overflow: hidden; border: 1px solid #d9dbde; border-radius: 8px; background: #fff;"><story /></div>',
    }),
  ],
  parameters: {
    layout: 'centered',
  },
  argTypes: {
    items: {
      control: 'object',
      description:
        'Flat selectable items or one-level groups with direct selectable children.',
    },
    modelValue: {
      control: 'select',
      options: [null, 'repeat', 'create-row', 'get-row', 'send-slack-message'],
      description: 'Value of the active leaf item.',
    },
    showSearch: {
      control: 'boolean',
      description: 'Displays the global action search input.',
    },
    searchPlaceholder: {
      control: 'text',
      description: 'Placeholder displayed in the search input.',
    },
    emptyText: {
      control: 'text',
      description: 'Message displayed when no items are visible.',
    },
    onSelect: {
      control: false,
      table: { category: 'Events' },
    },
    onDisabledClick: {
      control: false,
      table: { category: 'Events' },
    },
    onClose: {
      control: false,
      table: { category: 'Events' },
    },
  },
  args: {
    items: groupedDropdownItems,
    modelValue: null,
    showSearch: true,
    searchPlaceholder: 'Search actions',
    emptyText: 'No actions found',
    onSelect: fn(),
    onDisabledClick: fn(),
    onClose: fn(),
  },
}

export const Default = {
  render: renderMenu,
}

export const Selection = {
  args: {
    onSelect: fn(),
  },
  render: renderMenu,
  play: async ({ args, canvas, userEvent }) => {
    await userEvent.click(
      canvas.getByRole('menuitem', { name: /local baserow/i })
    )
    await userEvent.click(canvas.getByRole('menuitem', { name: /get row/i }))

    await expect(args.onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ value: 'get-row' })
    )
  },
}

export const WithoutSearch = {
  args: {
    showSearch: false,
  },
  render: renderMenu,
}
