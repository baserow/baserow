import type { Meta, StoryObj } from '@storybook/vue3'
import Badge from '@baserow/modules/core/components/Badge'

const meta = {
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
    },
    size: {
      control: 'select',
      options: ['regular', 'small', 'large'],
    },
    indicator: {
      control: 'boolean',
    },
    rounded: {
      control: 'boolean',
    },
    bold: {
      control: 'boolean',
    },
  },
  args: {
    color: 'cyan',
    size: 'regular',
    indicator: true,
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
} satisfies Meta<typeof Badge>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    color: 'neutral',
  },
  render: (args) => ({
    components: { Badge },
    setup() {
      return { args }
    },
    template: '<Badge v-bind="args">Label</Badge>',
  }),
}
