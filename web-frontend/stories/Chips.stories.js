import Chips from '@baserow/modules/core/components/Chips'

export default {
  title: 'Baserow/Chips',
  component: Chips,
  tags: ['autodocs'],
  argTypes: {
    active: {
      control: 'boolean',
      description: 'Active state',
    },
    disabled: {
      control: 'boolean',
      description: 'Disabled state',
    },
    icon: {
      control: 'text',
      description: 'Icon class name',
    },
  },
  args: {
    active: false,
    disabled: false,
    icon: '',
  },
}

export const Default = {
  render: (args) => ({
    components: { Chips },
    setup() {
      return { args }
    },
    template: '<Chips v-bind="args">Filter</Chips>',
  }),
}

export const Active = {
  args: {
    active: true,
  },
  render: (args) => ({
    components: { Chips },
    setup() {
      return { args }
    },
    template: '<Chips v-bind="args">Active Filter</Chips>',
  }),
}

export const WithIcon = {
  args: {
    icon: 'iconoir-filter-list',
  },
  render: (args) => ({
    components: { Chips },
    setup() {
      return { args }
    },
    template: '<Chips v-bind="args">Filter</Chips>',
  }),
}

export const States = {
  render: () => ({
    components: { Chips },
    template: `
      <div style="display: flex; gap: 10px; align-items: center;">
        <Chips>Default</Chips>
        <Chips active>Active</Chips>
        <Chips icon="iconoir-check">With Icon</Chips>
        <Chips disabled>Disabled</Chips>
        <Chips active icon="iconoir-star">Active Icon</Chips>
      </div>
    `,
  }),
}
