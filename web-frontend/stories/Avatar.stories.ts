import type { Meta, StoryObj } from '@storybook/vue3'
import Avatar from '@baserow/modules/core/components/Avatar'

const meta = {
  title: 'Baserow/Avatar',
  component: Avatar,
  tags: ['autodocs'],
} satisfies Meta<typeof Avatar>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: (args) => ({
    components: { Avatar },
    setup() {
      return { args }
    },
    template: '<Avatar v-bind="args" />',
  }),
}
