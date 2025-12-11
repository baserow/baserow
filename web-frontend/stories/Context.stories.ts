import type { Meta, StoryObj } from '@storybook/vue3'
import Context from '@baserow/modules/core/components/Context'

const meta = {
  title: 'Baserow/Context',
  component: Context,
  tags: ['autodocs'],
} satisfies Meta<typeof Context>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: (args) => ({
    components: { Context },
    setup() {
      return { args }
    },
    template: '<Context v-bind="args" />',
  }),
}
