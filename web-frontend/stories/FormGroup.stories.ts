import type { Meta, StoryObj } from '@storybook/vue3'
import FormGroup from '@baserow/modules/core/components/FormGroup'

const meta = {
  title: 'Baserow/Form Elements/FormGroup',
  component: FormGroup,
  tags: ['autodocs'],
} satisfies Meta<typeof FormGroup>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: (args) => ({
    components: { FormGroup },
    setup() {
      return { args }
    },
    template: '<FormGroup v-bind="args" />',
  }),
}
