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
      @enabled-protected-edit="values.hubspot_access_token = ''"
      @disable-protected-edit="values.hubspot_access_token = undefined"
    >
      <FormInput
        v-model="v$.values.hubspot_access_token.$model"
        :error="fieldHasErrors('hubspot_access_token')"
        :disabled="disabled"
        size="large"
        @blur="v$.values.hubspot_access_token.$touch"
      />
      <template #error>
        {{ v$.values.hubspot_access_token.$errors[0]?.$message }}
      </template>
    </FormGroup>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required, helpers } from '@vuelidate/validators'
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
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      allowedValues: ['hubspot_access_token'],
      values: {
        hubspot_access_token: this.update ? undefined : '',
      },
    }
  },
  validations() {
    return {
      values: {
        hubspot_access_token: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
      },
    }
  },
}
</script>
