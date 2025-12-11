import type { Meta, StoryObj } from '@storybook/vue3'
import Chips from '@baserow/modules/core/components/Chips'

const meta = {
  title: 'Baserow/Chips',
  component: Chips,
  tags: ['autodocs'],
} satisfies Meta<typeof Chips>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: (args) => ({
    components: { Chips },
    setup() {
      return { args }
    },
    template: '<Chips v-bind="args" />',
  }),
}
