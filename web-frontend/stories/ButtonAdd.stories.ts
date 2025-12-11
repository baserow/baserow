import type { Meta, StoryObj } from '@storybook/vue3'
import ButtonAdd from '@baserow/modules/core/components/ButtonAdd'

const meta = {
  title: 'Baserow/Buttons/ButtonAdd',
  component: ButtonAdd,
  tags: ['autodocs'],
} satisfies Meta<typeof ButtonAdd>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: (args) => ({
    components: { ButtonAdd },
    setup() {
      return { args }
    },
    template: '<ButtonAdd v-bind="args" />',
  }),
}
