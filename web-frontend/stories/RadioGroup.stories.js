import RadioGroup from '@baserow/modules/core/components/RadioGroup'

export default {
  title: 'Baserow/Form Elements/Radio/RadioGroup',
  component: RadioGroup,
  tags: ['autodocs'],
}

export const Default = {
  render: (args) => ({
    components: { RadioGroup },
    setup() {
      return { args }
    },
    template: '<RadioGroup v-bind="args" />',
  }),
}


