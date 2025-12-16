import RadioButton from '@baserow/modules/core/components/RadioButton'

export default {
  title: 'Baserow/Form Elements/Radio/RadioButton',
  component: RadioButton,
  tags: ['autodocs'],
}

export const Default = {
  render: (args) => ({
    components: { RadioButton },
    setup() {
      return { args }
    },
    template: '<RadioButton v-bind="args" />',
  }),
}


