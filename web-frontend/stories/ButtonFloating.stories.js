import ButtonFloating from '@baserow/modules/core/components/ButtonFloating'

export default {
  title: 'Baserow/Buttons/ButtonFloating',
  component: ButtonFloating,
  tags: ['autodocs'],
}

export const Default = {
  render: (args) => ({
    components: { ButtonFloating },
    setup() {
      return { args }
    },
    template: '<ButtonFloating v-bind="args" />',
  }),
}


