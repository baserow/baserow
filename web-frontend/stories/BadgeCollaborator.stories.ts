import type { Meta, StoryObj } from '@storybook/vue3'
import BadgeCollaborator from '@baserow/modules/core/components/BadgeCollaborator'

const meta = {
  title: 'Baserow/BadgeCollaborator',
  component: BadgeCollaborator,
  tags: ['autodocs'],
} satisfies Meta<typeof BadgeCollaborator>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: (args) => ({
    components: { BadgeCollaborator },
    setup() {
      return { args }
    },
    template: '<BadgeCollaborator v-bind="args" />',
  }),
}
