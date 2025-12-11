import type { Meta, StoryObj } from '@storybook/vue3'
import Button from '@baserow/modules/core/components/Button'

const meta = {
  title: 'Baserow/Buttons/Standard',
  component: Button,
  tags: ['autodocs'],
  argTypes: {
    tag: {
      control: 'radio',
      options: ['a', 'button', 'nuxt-link'],
    },
    type: {
      control: 'select',
      options: ['primary', 'secondary', 'danger', 'upload', 'ghost'],
    },
    size: {
      control: 'radio',
      options: ['tiny', 'small', 'regular', 'large', 'xlarge'],
    },
    icon: {
      control: 'text',
    },
    rel: {
      control: 'text',
    },
    href: {
      control: 'text',
    },
    target: {
      control: 'select',
      options: ['_blank', '_self', '_parent', '_top'],
    },
    loading: {
      control: 'boolean',
    },
    disabled: {
      control: 'boolean',
    },
    fullWidth: {
      control: 'boolean',
    },
  },
  args: {
    tag: 'button',
    type: 'primary',
    size: 'regular',
    icon: 'iconoir-gitlab-full',
    rel: null,
    href: '',
    target: null,
    loading: false,
    disabled: false,
    fullWidth: false,
  },
  parameters: {
    design: {
      type: 'figma',
      url: 'https://www.figma.com/file/W7R2rQW7ohsZMeHRfEcPFW/Design-Library?type=design&node-id=1-85&mode=design&t=ZFKwI59cTYQROI8S-0',
    },
  },
} satisfies Meta<typeof Button>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: (args) => ({
    components: { Button },
    setup() {
      return { args }
    },
    template: '<Button v-bind="args">Label</Button>',
  }),
}
