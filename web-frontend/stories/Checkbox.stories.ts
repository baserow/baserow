import type { Meta, StoryObj } from '@storybook/vue3'
import Checkbox from '@baserow/modules/core/components/Checkbox'

const meta = {
  title: 'Baserow/Form Elements/Checkbox',
  component: Checkbox,
  tags: ['autodocs'],
  argTypes: {
    checked: {
      control: 'boolean',
    },
    disabled: {
      control: 'boolean',
    },
    error: {
      control: 'boolean',
    },
    indeterminate: {
      control: 'boolean',
    },
  },
  args: {
    checked: false,
    disabled: false,
    error: false,
    indeterminate: false,
  },
  parameters: {
    backgrounds: {
      default: 'white',
      values: [
        { name: 'white', value: '#ffffff' },
        { name: 'light', value: '#eeeeee' },
        { name: 'dark', value: '#222222' },
      ],
    },
    design: {
      type: 'figma',
      url: 'https://www.figma.com/file/W7R2rQW7ohsZMeHRfEcPFW/Design-Library?node-id=54%3A919&mode=dev',
    },
  },
} satisfies Meta<typeof Checkbox>

export default meta
type Story = StoryObj<typeof meta>

export const CheckboxStory: Story = {
  args: {
    checked: true,
  },
  render: (args) => ({
    components: { Checkbox },
    setup() {
      return { args }
    },
    template: '<Checkbox v-bind="args">Label</Checkbox>',
  }),
}
