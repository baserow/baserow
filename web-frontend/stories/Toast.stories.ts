import type { Meta, StoryObj } from '@storybook/vue3'
import Toast from '@baserow/modules/core/components/Toast'

const meta = {
  title: 'Baserow/Toast',
  component: Toast,
  tags: ['autodocs'],
} satisfies Meta<typeof Toast>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: (args) => ({
    components: { Toast },
    setup() {
      return { args }
    },
    template: '<Toast v-bind="args" />',
  }),
}
