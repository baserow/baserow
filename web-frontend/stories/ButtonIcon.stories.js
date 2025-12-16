import ButtonIcon from '@baserow/modules/core/components/ButtonIcon'

export default {
  title: 'Baserow/Buttons/ButtonIcon',
  component: ButtonIcon,
  tags: ['autodocs'],
}

export const Default = {
  render: (args) => ({
    components: { ButtonIcon },
    setup() {
      return { args }
    },
    template: '<ButtonIcon v-bind="args" />',
  }),
}


