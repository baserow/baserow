import RadioCard from '@baserow/modules/core/components/RadioCard'

export default {
  title: 'Baserow/Form Elements/Radio/RadioCard',
  component: RadioCard,
  tags: ['autodocs'],
}

export const Default = {
  render: (args) => ({
    components: { RadioCard },
    setup() {
      return { args }
    },
    template: '<RadioCard v-bind="args" />',
  }),
}


