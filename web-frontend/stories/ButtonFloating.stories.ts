import type { Meta, StoryObj } from '@storybook/vue3'
import ButtonFloating from '@baserow/modules/core/components/ButtonFloating'

const meta = {
  title: 'Baserow/Buttons/ButtonFloating',
  component: ButtonFloating,
  tags: ['autodocs'],
} satisfies Meta<typeof ButtonFloating>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: (args) => ({
    components: { ButtonFloating },
    setup() {
      return { args }
    },
    template: '<ButtonFloating v-bind="args" />',
  }),
}
