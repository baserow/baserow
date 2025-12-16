import SegmentControl from '@baserow/modules/core/components/SegmentControl'

export default {
  title: 'Baserow/Form Elements/SegmentControl',
  component: SegmentControl,
  tags: ['autodocs'],
}

export const Default = {
  render: (args) => ({
    components: { SegmentControl },
    setup() {
      return { args }
    },
    template: '<SegmentControl v-bind="args" />',
  }),
}


