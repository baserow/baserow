import SegmentControl from '@baserow/modules/core/components/SegmentControl'

export default {
  title: 'Baserow/Form Elements/SegmentControl',
  component: SegmentControl,
  tags: ['autodocs'],
  argTypes: {
    segments: {
      control: 'object',
      description: 'Array of objects with a label and an optional icon',
    },
    initialActiveIndex: {
      control: 'number',
    },
    type: {
      control: {
        type: 'select',
        options: ['regular', 'rounded', 'pills'],
      },
    },
    size: {
      control: {
        type: 'select',
        options: ['regular', 'small', 'large'],
      },
    },
    transparent: {
      control: 'boolean',
    },
    iconsOnly: {
      control: 'boolean',
    },
  },
  args: {
    segments: [{ label: 'Daily' }, { label: 'Weekly' }, { label: 'Monthly' }],
    initialActiveIndex: 0,
    type: 'regular',
    size: 'regular',
    transparent: false,
    iconsOnly: false,
  },
}

const render = (args) => ({
  components: { SegmentControl },
  setup() {
    return { args }
  },
  template: '<SegmentControl v-bind="args" />',
})

export const Default = { render }

export const Pills = {
  render,
  args: {
    type: 'pills',
    segments: [
      { label: 'Official templates', icon: 'baserow-icon-templates' },
      { label: 'Your templates', icon: 'iconoir-box' },
    ],
  },
}
