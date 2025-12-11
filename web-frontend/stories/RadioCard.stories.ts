import type { Meta, StoryObj } from '@storybook/vue3'
import RadioCard from '@baserow/modules/core/components/RadioCard'

const meta = {
  title: 'Baserow/Form Elements/Radio/RadioCard',
  component: RadioCard,
  tags: ['autodocs'],
} satisfies Meta<typeof RadioCard>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: (args) => ({
    components: { RadioCard },
    setup() {
      return { args }
    },
    template: '<RadioCard v-bind="args" />',
  }),
}
