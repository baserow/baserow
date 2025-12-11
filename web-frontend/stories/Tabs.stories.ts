import type { Meta, StoryObj } from '@storybook/vue3'
import Tabs from '@baserow/modules/core/components/Tabs'

const meta = {
  title: 'Baserow/Tabs',
  component: Tabs,
  tags: ['autodocs'],
} satisfies Meta<typeof Tabs>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: (args) => ({
    components: { Tabs },
    setup() {
      return { args }
    },
    template: '<Tabs v-bind="args" />',
  }),
}
