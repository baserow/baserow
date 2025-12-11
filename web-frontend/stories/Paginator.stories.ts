import type { Meta, StoryObj } from '@storybook/vue3'
import Paginator from '@baserow/modules/core/components/Paginator'

const meta = {
  title: 'Baserow/Paginator',
  component: Paginator,
  tags: ['autodocs'],
  argTypes: {
    page: {
      control: 'number',
    },
    totalPages: {
      control: 'number',
    },
  },
  args: {
    page: 3,
    totalPages: 10,
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
      url: 'https://www.figma.com/file/W7R2rQW7ohsZMeHRfEcPFW/Design-Library?node-id=1204%3A4132&mode=dev',
    },
  },
} satisfies Meta<typeof Paginator>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: (args) => ({
    components: { Paginator },
    setup() {
      return { args }
    },
    template: '<Paginator v-bind="args" />',
  }),
}
