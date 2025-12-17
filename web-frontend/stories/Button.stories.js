import Button from '@baserow/modules/core/components/Button'

export default {
  title: 'Baserow/Buttons/Standard',
  component: Button,
  tags: ['autodocs'],
  argTypes: {
    tag: {
      control: 'radio',
      options: ['a', 'button', 'nuxt-link'],
      description: 'The HTML tag to use for the button',
    },
    type: {
      control: 'select',
      options: ['primary', 'secondary', 'danger', 'upload', 'ghost'],
      description: 'The visual style variant of the button',
    },
    size: {
      control: 'radio',
      options: ['tiny', 'small', 'regular', 'large', 'xlarge'],
      description: 'The size of the button',
    },
    icon: {
      control: 'text',
      description: 'Icon class to display before the label',
    },
    appendIcon: {
      control: 'text',
      description: 'Icon class to display after the label',
    },
    loading: {
      control: 'boolean',
      description: 'Show a loading spinner instead of content',
    },
    disabled: {
      control: 'boolean',
      description: 'Disable the button',
    },
    fullWidth: {
      control: 'boolean',
      description: 'Make the button take the full width of its container',
    },
    active: {
      control: 'boolean',
      description: 'Show the button in active state',
    },
    href: {
      control: 'text',
      description: 'URL if tag is "a"',
    },
    target: {
      control: 'select',
      options: ['_blank', '_self', '_parent', '_top'],
      description: 'Target attribute if tag is "a"',
    },
  },
  args: {
    tag: 'button',
    type: 'primary',
    size: 'regular',
    icon: '',
    appendIcon: '',
    loading: false,
    disabled: false,
    fullWidth: false,
    active: false,
  },
  parameters: {
    design: {
      type: 'figma',
      url: 'https://www.figma.com/file/W7R2rQW7ohsZMeHRfEcPFW/Design-Library?type=design&node-id=1-85&mode=design&t=ZFKwI59cTYQROI8S-0',
    },
  },
}

export const Default = {
  render: (args) => ({
    components: { Button },
    setup() {
      return { args }
    },
    template: '<Button v-bind="args">Label</Button>',
  }),
}

export const AllTypes = {
  render: () => ({
    components: { Button },
    template: `
      <div style="display: flex; gap: 10px; flex-wrap: wrap;">
        <Button type="primary">Primary</Button>
        <Button type="secondary">Secondary</Button>
        <Button type="danger">Danger</Button>
        <Button type="upload">Upload</Button>
        <Button type="ghost">Ghost</Button>
      </div>
    `,
  }),
}

export const AllSizes = {
  render: () => ({
    components: { Button },
    template: `
      <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
        <Button size="tiny">Tiny</Button>
        <Button size="small">Small</Button>
        <Button size="regular">Regular</Button>
        <Button size="large">Large</Button>
        <Button size="xlarge">Extra Large</Button>
      </div>
    `,
  }),
}

export const WithIcons = {
  render: () => ({
    components: { Button },
    template: `
      <div style="display: flex; gap: 10px; flex-wrap: wrap;">
        <Button icon="iconoir-user">Prefix Icon</Button>
        <Button append-icon="iconoir-arrow-right">Suffix Icon</Button>
        <Button icon="iconoir-check" append-icon="iconoir-arrow-right">Both Icons</Button>
        <Button icon="iconoir-plus" /> <!-- Icon only -->
      </div>
    `,
  }),
}

export const States = {
  render: () => ({
    components: { Button },
    template: `
      <div style="display: flex; gap: 10px; flex-wrap: wrap;">
        <Button>Normal</Button>
        <Button active>Active</Button>
        <Button disabled>Disabled</Button>
        <Button loading>Loading</Button>
      </div>
    `,
  }),
}

export const FullWidth = {
  render: (args) => ({
    components: { Button },
    template: `
      <div style="width: 300px; padding: 20px; border: 1px dashed #ccc;">
        <Button full-width>Full Width Button</Button>
      </div>
    `,
  }),
}

export const AsLink = {
  render: (args) => ({
    components: { Button },
    template: `
      <div style="display: flex; gap: 10px;">
        <Button tag="a" href="https://baserow.io" target="_blank" icon="iconoir-link">
          Baserow Website
        </Button>
        <Button tag="a" href="#" type="secondary">
          Internal Link
        </Button>
      </div>
    `,
  }),
}
