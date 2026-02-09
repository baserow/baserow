import Badge from '@baserow/modules/core/components/Badge'

export default {
  title: 'Baserow/Badges',
  component: Badge,
  tags: ['autodocs'],
  argTypes: {
    color: {
      control: 'select',
      options: [
        'cyan',
        'green',
        'yellow',
        'red',
        'magenta',
        'purple',
        'neutral',
      ],
      description: 'The color scheme of the badge',
    },
    size: {
      control: 'select',
      options: ['regular', 'small', 'large'],
      description: 'The size of the badge',
    },
    indicator: {
      control: 'boolean',
      description: 'Display a small indicator dot on the badge if true',
    },
    rounded: {
      control: 'boolean',
      description: 'Display a more rounded badge if true',
    },
    bold: {
      control: 'boolean',
      description: 'Make the text of the badge bold if true',
    },
  },
  args: {
    color: 'neutral',
    size: 'regular',
    indicator: false,
    rounded: false,
    bold: false,
  },
  parameters: {
    backgrounds: {
      default: 'white',
      values: [
        { name: 'white', value: '#ffffff' },
        { name: 'light', value: '#eeeeee' },
        { name: 'dark', value: '#222222' },
      ],
    },
    design: {
      type: 'figma',
      url: 'https://www.figma.com/file/W7R2rQW7ohsZMeHRfEcPFW/Design-Library?node-id=53%3A21&mode=dev',
    },
  },
}

export const Default = {
  render: (args) => ({
    components: { Badge },
    setup() {
      return { args }
    },
    template: '<Badge v-bind="args">Label</Badge>',
  }),
}

export const AllColors = {
  render: () => ({
    components: { Badge },
    template: `
      <div style="display: flex; gap: 8px; flex-wrap: wrap;">
        <Badge color="neutral">Neutral</Badge>
        <Badge color="cyan">Cyan</Badge>
        <Badge color="green">Green</Badge>
        <Badge color="yellow">Yellow</Badge>
        <Badge color="red">Red</Badge>
        <Badge color="magenta">Magenta</Badge>
        <Badge color="purple">Purple</Badge>
      </div>
    `,
  }),
}

export const AllSizes = {
  render: () => ({
    components: { Badge },
    template: `
      <div style="display: flex; align-items: center; gap: 8px;">
        <Badge size="small">Small</Badge>
        <Badge size="regular">Regular</Badge>
        <Badge size="large">Large</Badge>
      </div>
    `,
  }),
}

export const WithIndicator = {
  args: {
    indicator: true,
  },
  render: (args) => ({
    components: { Badge },
    setup() {
      return { args }
    },
    template: `
      <div style="display: flex; gap: 8px; flex-wrap: wrap;">
        <Badge color="green" :indicator="true">Active</Badge>
        <Badge color="red" :indicator="true">Inactive</Badge>
        <Badge color="yellow" :indicator="true">Pending</Badge>
        <Badge color="neutral" :indicator="true">Offline</Badge>
      </div>
    `,
  }),
}

export const Rounded = {
  args: {
    rounded: true,
  },
  render: (args) => ({
    components: { Badge },
    setup() {
      return { args }
    },
    template: `
      <div style="display: flex; gap: 8px;">
        <Badge :rounded="true" color="cyan">Rounded Cyan</Badge>
        <Badge :rounded="true" color="purple">Rounded Purple</Badge>
      </div>
    `,
  }),
}

export const BoldText = {
  args: {
    bold: true,
  },
  render: (args) => ({
    components: { Badge },
    setup() {
      return { args }
    },
    template: `
      <div style="display: flex; gap: 8px;">
        <Badge :bold="true" color="red">Urgent</Badge>
        <Badge :bold="true" color="green">Success</Badge>
      </div>
    `,
  }),
}

export const Combinations = {
  render: () => ({
    components: { Badge },
    template: `
      <div style="display: flex; flex-direction: column; gap: 16px;">
        <div style="display: flex; gap: 8px; align-items: center;">
          <Badge color="green" size="small" :indicator="true" :bold="true">Small Bold Active</Badge>
          <Badge color="red" size="large" :rounded="true">Large Rounded Error</Badge>
        </div>
        <div style="display: flex; gap: 8px; align-items: center;">
          <Badge color="purple" :indicator="true" :rounded="true">Rounded Indicator</Badge>
          <Badge color="cyan" size="small" :bold="true">Small Bold</Badge>
        </div>
      </div>
    `,
  }),
}
