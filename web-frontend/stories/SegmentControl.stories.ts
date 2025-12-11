import type { Meta, StoryObj } from '@storybook/vue3'
import SegmentControl from '@baserow/modules/core/components/SegmentControl'

const meta = {
  title: 'Baserow/Form Elements/SegmentControl',
  component: SegmentControl,
  tags: ['autodocs'],
} satisfies Meta<typeof SegmentControl>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: (args) => ({
    components: { SegmentControl },
    setup() {
      return { args }
    },
    template: '<SegmentControl v-bind="args" />',
  }),
}
