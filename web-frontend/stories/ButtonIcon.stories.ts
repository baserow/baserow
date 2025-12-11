import type { Meta, StoryObj } from '@storybook/vue3'
import ButtonIcon from '@baserow/modules/core/components/ButtonIcon'

const meta = {
  title: 'Baserow/Buttons/ButtonIcon',
  component: ButtonIcon,
  tags: ['autodocs'],
} satisfies Meta<typeof ButtonIcon>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: (args) => ({
    components: { ButtonIcon },
    setup() {
      return { args }
    },
    template: '<ButtonIcon v-bind="args" />',
  }),
}
