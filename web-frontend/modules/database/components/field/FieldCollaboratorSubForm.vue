<template>
  <FormGroup>
    <Checkbox v-model="values.notify_user_when_added">
      {{ $t('fieldCollaboratorSubForm.notifyUserWhenAdded') }}
    </Checkbox>
  </FormGroup>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import fieldSubForm from '@baserow/modules/database/mixins/fieldSubForm'

export default {
  name: 'FieldCollaboratorSubForm',
  mixins: [form, fieldSubForm],
  data() {
    return {
      allowedValues: ['notify_user_when_added'],
      values: {
        notify_user_when_added: true,
      },
    }
  },
  methods: {
    isFormValid() {
      return true
    },
  },
}
</script>
