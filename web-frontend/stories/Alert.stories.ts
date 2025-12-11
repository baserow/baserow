import type { Meta, StoryObj } from '@storybook/vue3'
import Alert from '@baserow/modules/core/components/Alert'

const meta = {
  title: 'Baserow/Alert',
  component: Alert,
  tags: ['autodocs'],
} satisfies Meta<typeof Alert>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: (args) => ({
    components: { Alert },
    setup() {
      return { args }
    },
    template: '<Alert v-bind="args" />',
  }),
}
