import ButtonAdd from '@baserow/modules/core/components/ButtonAdd'

export default {
  title: 'Baserow/Buttons/ButtonAdd',
  component: ButtonAdd,
  tags: ['autodocs'],
}

export const Default = {
  render: (args) => ({
    components: { ButtonAdd },
    setup() {
      return { args }
    },
    template: '<ButtonAdd v-bind="args" />',
  }),
}


