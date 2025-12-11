import type { Meta, StoryObj } from '@storybook/vue3'
import ButtonText from '@baserow/modules/core/components/ButtonText'

const meta = {
  title: 'Baserow/Buttons/ButtonText',
  component: ButtonText,
  tags: ['autodocs'],
} satisfies Meta<typeof ButtonText>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: (args) => ({
    components: { ButtonText },
    setup() {
      return { args }
    },
    template: '<ButtonText v-bind="args" />',
  }),
}
