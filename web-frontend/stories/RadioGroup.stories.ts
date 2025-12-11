import type { Meta, StoryObj } from '@storybook/vue3'
import RadioGroup from '@baserow/modules/core/components/RadioGroup'

const meta = {
  title: 'Baserow/Form Elements/Radio/RadioGroup',
  component: RadioGroup,
  tags: ['autodocs'],
} satisfies Meta<typeof RadioGroup>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: (args) => ({
    components: { RadioGroup },
    setup() {
      return { args }
    },
    template: '<RadioGroup v-bind="args" />',
  }),
}
