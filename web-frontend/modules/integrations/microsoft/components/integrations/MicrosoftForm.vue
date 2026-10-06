<template>
  <div>
    <OAuth2CredentialsFields
      v-model:client-id="values.client_id"
      v-model:client-secret="values.client_secret"
      :has-client-secret="hasClientSecret"
      :client-id-error="getFirstErrorMessage('client_id')"
      :client-secret-error="getFirstErrorMessage('client_secret')"
    />
    <FormGroup
      required
      :label="$t('microsoftForm.tenantLabel')"
      :helper-text="$t('microsoftForm.tenantHelp')"
      small-label
      class="margin-bottom-2"
      :error-message="getFirstErrorMessage('tenant')"
    >
      <FormInput
        v-model="values.tenant"
        :placeholder="$t('microsoftForm.tenantPlaceholder')"
      />
    </FormGroup>
    <OAuth2ConnectSection :integration="defaultValues" provider="Microsoft" />
    <hr />
    <FormGroup
      :label="$t('microsoftForm.supportHeading')"
      small-label
      class="margin-top-3 margin-bottom-2"
    >
      <p class="margin-bottom-2">
        {{ $t('microsoftForm.supportDescription') }}
      </p>
      <Expandable card class="margin-bottom-2">
        <template #header="{ toggle, expanded }">
          <div class="flex flex-100 justify-content-space-between">
            <a @click="toggle">
              {{ $t('microsoftForm.setupHeading') }}
              <Icon
                :icon="
                  expanded
                    ? 'iconoir-nav-arrow-down'
                    : 'iconoir-nav-arrow-right'
                "
                type="secondary"
              />
            </a>
          </div>
        </template>
        <template #default>
          <ol class="integration-setup-steps">
            <li>
              <i18n-t scope="global" keypath="microsoftForm.setupStep1">
                <template #link>
                  <a
                    href="https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade"
                    target="_blank"
                    >{{ $t('microsoftForm.setupStep1Link') }}</a
                  >
                </template>
              </i18n-t>
            </li>
            <li>{{ $t('microsoftForm.setupStep2') }}</li>
            <li>{{ $t('microsoftForm.setupStep3') }}</li>
            <li>
              <i18n-t scope="global" keypath="microsoftForm.setupStep4">
                <template #scopes>
                  <pre>
Mail.Send Calendars.ReadWrite ChannelMessage.Send User.Read offline_access</pre
                  >
                </template>
              </i18n-t>
            </li>
            <li>{{ $t('microsoftForm.setupStep5') }}</li>
          </ol>
        </template>
      </Expandable>
      <Expandable card class="margin-bottom-2">
        <template #header="{ toggle, expanded }">
          <div class="flex flex-100 justify-content-space-between">
            <a @click="toggle">
              {{ $t('microsoftForm.teamsHeading') }}
              <Icon
                :icon="
                  expanded
                    ? 'iconoir-nav-arrow-down'
                    : 'iconoir-nav-arrow-right'
                "
                type="secondary"
              />
            </a>
          </div>
        </template>
        <template #default>
          <ol class="integration-setup-steps">
            <li>{{ $t('microsoftForm.teamsStep1') }}</li>
            <li>
              <i18n-t scope="global" keypath="microsoftForm.teamsStep2">
                <template #example>
                  <pre>groupId=…</pre>
                </template>
              </i18n-t>
            </li>
            <li>
              <i18n-t scope="global" keypath="microsoftForm.teamsStep3">
                <template #example>
                  <pre>19:…@thread.tacv2</pre>
                </template>
              </i18n-t>
            </li>
          </ol>
        </template>
      </Expandable>
    </FormGroup>
  </div>
</template>

<script>
import { helpers } from '@vuelidate/validators'
import { useVuelidate } from '@vuelidate/core'
import oauth2IntegrationForm from '@baserow/modules/integrations/oauth2/oauth2IntegrationForm'
import OAuth2ConnectSection from '@baserow/modules/integrations/oauth2/components/integrations/OAuth2ConnectSection'
import OAuth2CredentialsFields from '@baserow/modules/integrations/oauth2/components/integrations/OAuth2CredentialsFields'

export default {
  name: 'MicrosoftForm',
  components: { OAuth2ConnectSection, OAuth2CredentialsFields },
  mixins: [oauth2IntegrationForm],
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      values: { client_id: '', client_secret: null, tenant: 'common' },
      allowedValues: ['client_id', 'client_secret', 'tenant'],
    }
  },
  validations() {
    return {
      values: {
        client_id: {
          required: helpers.withMessage(
            this.$t('oauth2Credentials.required'),
            (value) => !!value
          ),
        },
        client_secret: {
          required: helpers.withMessage(
            this.$t('oauth2Credentials.required'),
            (value) => this.hasClientSecret || !!value
          ),
        },
        tenant: {
          required: helpers.withMessage(
            this.$t('oauth2Credentials.required'),
            (value) => !!value
          ),
        },
      },
    }
  },
}
</script>
