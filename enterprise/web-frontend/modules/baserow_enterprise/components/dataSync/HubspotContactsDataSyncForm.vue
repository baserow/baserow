<template>
  <form @submit.prevent="submit">
    <FormGroup
      :error="fieldHasErrors('hubspot_access_token')"
      :label="$t('hubspotContactsDataSync.accessToken')"
      required
      class="margin-bottom-2"
      :helper-text="$t('hubspotContactsDataSync.accessTokenHelper')"
      :protected-edit="update"
      small-label
    >
      <FormInput
        v-model="values.hubspot_access_token"
        :error="fieldHasErrors('hubspot_access_token')"
        :disabled="disabled"
        size="large"
        @blur="$v.values.hubspot_access_token.$touch()"
      />
      <template #error>
        <span
          v-if="
            $v.values.hubspot_access_token.$dirty &&
            !$v.values.hubspot_access_token.required
          "
        >
          {{ $t('error.requiredField') }}
        </span>
      </template>
    </FormGroup>
  </form>
</template>

<script>
import { required } from 'vuelidate/lib/validators'
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'HubspotContactsDataSyncForm',
  mixins: [form],
  props: {
    update: {
      type: Boolean,
      required: false,
      default: false,
    },
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      allowedValues: ['hubspot_access_token'],
      values: {
        hubspot_access_token: '',
      },
    }
  },
  validations: {
    values: {
      hubspot_access_token: { required },
    },
  },
}
</script>
