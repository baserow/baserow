import type { Meta, StoryObj } from '@storybook/vue3'
import FormInput from '@baserow/modules/core/components/FormInput'

const meta = {
  title: 'Baserow/Form Elements/Input',
  component: FormInput,
  tags: ['autodocs'],
  argTypes: {
    suffix: {
      control: 'text',
    },
    label: {
      control: 'text',
    },
    size: {
      control: 'select',
      options: ['small', 'regular', 'large', 'xlarge'],
    },
    placeholder: {
      control: 'text',
    },
    required: {
      control: 'boolean',
    },
    error: {
      control: 'boolean',
    },
    monospace: {
      control: 'boolean',
    },
    disabled: {
      control: 'boolean',
    },
    loading: {
      control: 'boolean',
    },
    iconLeft: {
      control: 'text',
    },
    iconRight: {
      control: 'text',
    },
    type: {
      control: 'select',
      options: ['text', 'number', 'password', 'email', 'url'],
    },
    textInvisible: {
      control: 'boolean',
    },
  },
  args: {
    suffix: '',
    label: 'Label',
    size: 'regular',
    placeholder: 'Placeholder text...',
    required: false,
    error: false,
    monospace: false,
    disabled: false,
    loading: false,
    iconLeft: 'iconoir-db',
    iconRight: 'iconoir-db',
    type: 'text',
    textInvisible: false,
  },
  parameters: {
    backgrounds: {
      default: 'light',
      values: [
        { name: 'white', value: '#ffffff' },
        { name: 'light', value: '#eeeeee' },
        { name: 'dark', value: '#222222' },
      ],
    },
    design: {
      type: 'figma',
      url: 'https://www.figma.com/file/W7R2rQW7ohsZMeHRfEcPFW/Design-Library?node-id=1%3A87&mode=dev',
    },
  },
} satisfies Meta<typeof FormInput>

export default meta
type Story = StoryObj<typeof meta>

export const Input: Story = {
  render: (args) => ({
    components: { FormInput },
    setup() {
      return { args }
    },
    template: '<FormInput v-bind="args" />',
  }),
}

export const WithSuffix: Story = {
  args: {
    iconRight: '',
    suffix: '.com',
  },
  render: (args) => ({
    components: { FormInput },
    setup() {
      return { args }
    },
    template: `
      <FormInput v-bind="args">
        <template v-if="args.suffix" #suffix>{{ args.suffix }}</template>
      </FormInput>
    `,
  }),
}
