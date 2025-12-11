import type { Meta, StoryObj } from '@storybook/vue3'
import BadgeCounter from '@baserow/modules/core/components/BadgeCounter'

const meta = {
  title: 'Baserow/BadgeCounter',
  component: BadgeCounter,
  tags: ['autodocs'],
} satisfies Meta<typeof BadgeCounter>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: (args) => ({
    components: { BadgeCounter },
    setup() {
      return { args }
    },
    template: '<BadgeCounter v-bind="args" />',
  }),
}
