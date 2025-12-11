import type { Meta, StoryObj } from '@storybook/vue3'
import Radio from '@baserow/modules/core/components/Radio'

const meta = {
  title: 'Baserow/Form Elements/Radio/Radio',
  component: Radio,
  tags: ['autodocs'],
  argTypes: {
    modelValue: {
      control: 'text',
    },
    value: {
      control: 'text',
    },
    disabled: {
      control: 'boolean',
    },
    loading: {
      control: 'boolean',
    },
  },
  args: {
    modelValue: '',
    value: 'option1',
    disabled: false,
    loading: false,
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
      url: 'https://www.figma.com/file/W7R2rQW7ohsZMeHRfEcPFW/Design-Library?node-id=53%3A1852&mode=dev',
    },
  },
} satisfies Meta<typeof Radio>

export default meta
type Story = StoryObj<typeof meta>

export const RadioStory: Story = {
  render: (args) => ({
    components: { Radio },
    setup() {
      return { args }
    },
    template: '<Radio v-bind="args">Label</Radio>',
  }),
}
