import ButtonText from '@baserow/modules/core/components/ButtonText'

export default {
  title: 'Baserow/Buttons/ButtonText',
  component: ButtonText,
  tags: ['autodocs'],
}

export const Default = {
  render: (args) => ({
    components: { ButtonText },
    setup() {
      return { args }
    },
    template: '<ButtonText v-bind="args" />',
  }),
}


