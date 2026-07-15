import { expect, fn } from 'storybook/test'

import Badge from '@baserow/modules/core/components/Badge'
import MenuList from '@baserow/modules/core/components/MenuList'

import { compactMenuListItems, menuListItems } from './menuListFixtures'

const renderMenu = (args) => ({
  components: { MenuList },
  setup() {
    return { args }
  },
  template: `
    <MenuList v-bind="args" />
  `,
})

export default {
  title: 'Baserow/Menus/MenuList',
  component: MenuList,
  tags: ['autodocs'],
  decorators: [
    () => ({
      template:
        '<div style="width: 380px; overflow: hidden; border: 1px solid #d9dbde; border-radius: 8px;"><story /></div>',
    }),
  ],
  parameters: {
    layout: 'centered',
  },
  argTypes: {
    items: {
      control: 'object',
      description: 'Flat menu items.',
    },
    modelValue: {
      control: 'text',
      description: 'Value of the active item.',
    },
    searchable: {
      control: 'boolean',
      description: 'Displays the search input.',
    },
    searchPlaceholder: {
      control: 'text',
      description: 'Placeholder displayed in the search input.',
    },
    emptyText: {
      control: 'text',
      description: 'Message displayed when no items are visible.',
    },
    showDescriptions: {
      control: 'boolean',
      description: 'Displays item descriptions when available.',
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
    items: menuListItems,
    modelValue: null,
    searchable: true,
    searchPlaceholder: 'Search actions',
    emptyText: 'No actions found',
    showDescriptions: true,
    onSelect: fn(),
    onDisabledClick: fn(),
    onClose: fn(),
  },
}

export const Default = {
  render: renderMenu,
}

export const Compact = {
  args: {
    items: compactMenuListItems,
    modelValue: 'refresh-data',
    searchable: false,
    showDescriptions: false,
  },
  render: renderMenu,
}

export const Selection = {
  args: {
    onSelect: fn(),
  },
  render: renderMenu,
  play: async ({ args, canvas, userEvent }) => {
    await userEvent.click(canvas.getByRole('menuitem', { name: /get row/i }))
    await expect(args.onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ value: 'get-row' })
    )
  },
}

export const Search = {
  render: renderMenu,
  play: async ({ canvas, userEvent }) => {
    await userEvent.type(canvas.getByRole('searchbox'), 'message')
    await expect(
      canvas.getByRole('menuitem', { name: /send email/i })
    ).toBeInTheDocument()
    await expect(
      canvas.queryByRole('menuitem', { name: /create row/i })
    ).not.toBeInTheDocument()
  },
}

export const DisabledItem = {
  args: {
    onDisabledClick: fn(),
    onSelect: fn(),
  },
  render: renderMenu,
  play: async ({ args, canvas, userEvent }) => {
    await userEvent.click(
      canvas.getByRole('menuitem', { name: /execute code/i })
    )
    await expect(args.onDisabledClick).toHaveBeenCalledWith(
      expect.objectContaining({ value: 'execute-code' })
    )
    await expect(args.onSelect).not.toHaveBeenCalled()
  },
}

export const CustomMetadata = {
  render: (args) => ({
    components: { Badge, MenuList },
    setup() {
      return { args }
    },
    template: `
      <MenuList v-bind="args">
        <template #item-meta="{ item }">
          <Badge v-if="item.meta?.badge" color="neutral" size="small">
            {{ item.meta.badge }}
          </Badge>
        </template>
      </MenuList>
    `,
  }),
}

export const Empty = {
  args: {
    items: [],
    searchable: false,
    emptyText: 'No actions available',
  },
  render: renderMenu,
}
