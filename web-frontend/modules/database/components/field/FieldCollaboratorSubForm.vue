<template>
  <FormGroup>
    <Checkbox v-model="values.notify_user_when_added">
      {{ $t('fieldCollaboratorSubForm.notifyUserWhenAdded') }}
    </Checkbox>
    <Checkbox
      v-if="$featureFlagIsEnabled(FF_IDENTITIES)"
      v-model="values.include_identities"
    >
      {{ $t('fieldCollaboratorSubForm.includeIdentities') }}
    </Checkbox>
    <p v-if="removesIdentities" class="control__description">
      {{ $t('fieldCollaboratorSubForm.removesIdentities') }}
    </p>
  </FormGroup>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import fieldSubForm from '@baserow/modules/database/mixins/fieldSubForm'
import { FF_IDENTITIES } from '@baserow/modules/core/plugins/featureFlags'

export default {
  name: 'FieldCollaboratorSubForm',
  mixins: [form, fieldSubForm],
  data() {
    return {
      FF_IDENTITIES,
      allowedValues: ['notify_user_when_added', 'include_identities'],
      values: {
        notify_user_when_added: true,
        include_identities: false,
      },
    }
  },
  computed: {
    removesIdentities() {
      return (
        this.defaultValues.include_identities && !this.values.include_identities
      )
    },
  },
  methods: {
    isFormValid() {
      return true
    },
  },
}
</script>
