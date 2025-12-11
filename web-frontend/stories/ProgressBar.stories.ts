import type { Meta, StoryObj } from '@storybook/vue3'
import ProgressBar from '@baserow/modules/core/components/ProgressBar'

const meta = {
  title: 'Baserow/ProgressBar',
  component: ProgressBar,
  tags: ['autodocs'],
} satisfies Meta<typeof ProgressBar>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: (args) => ({
    components: { ProgressBar },
    setup() {
      return { args }
    },
    template: '<ProgressBar v-bind="args" />',
  }),
}
