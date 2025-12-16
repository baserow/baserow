import FormGroup from '@baserow/modules/core/components/FormGroup'

export default {
  title: 'Baserow/Form Elements/FormGroup',
  component: FormGroup,
  tags: ['autodocs'],
}

export const Default = {
  render: (args) => ({
    components: { FormGroup },
    setup() {
      return { args }
    },
    template: '<FormGroup v-bind="args" />',
  }),
}


