import type { Meta, StoryObj } from '@storybook/vue3'
import RadioButton from '@baserow/modules/core/components/RadioButton'

const meta = {
  title: 'Baserow/Form Elements/Radio/RadioButton',
  component: RadioButton,
  tags: ['autodocs'],
} satisfies Meta<typeof RadioButton>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: (args) => ({
    components: { RadioButton },
    setup() {
      return { args }
    },
    template: '<RadioButton v-bind="args" />',
  }),
}
