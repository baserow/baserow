<template>
  <div>
    <OAuth2CredentialsFields
      v-model:client-id="values.client_id"
      v-model:client-secret="values.client_secret"
      :has-client-secret="hasClientSecret"
      :client-id-error="getFirstErrorMessage('client_id')"
      :client-secret-error="getFirstErrorMessage('client_secret')"
    />
    <OAuth2ConnectSection :integration="defaultValues" provider="Google" />
    <hr />
    <FormGroup
      :label="$t('googleForm.supportHeading')"
      small-label
      class="margin-top-3 margin-bottom-2"
    >
      <p class="margin-bottom-2">{{ $t('googleForm.supportDescription') }}</p>
      <Expandable card class="margin-bottom-2">
        <template #header="{ toggle, expanded }">
          <div class="flex flex-100 justify-content-space-between">
            <a @click="toggle">
              {{ $t('googleForm.setupHeading') }}
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
              <i18n-t scope="global" keypath="googleForm.setupStep1">
                <template #link>
                  <a
                    href="https://console.cloud.google.com/apis/credentials"
                    target="_blank"
                    >{{ $t('googleForm.setupStep1Link') }}</a
                  >
                </template>
              </i18n-t>
            </li>
            <li>{{ $t('googleForm.setupStep2') }}</li>
            <li>{{ $t('googleForm.setupStep3') }}</li>
            <li>{{ $t('googleForm.setupStep4') }}</li>
            <li>{{ $t('googleForm.setupStep5') }}</li>
          </ol>
        </template>
      </Expandable>
      <Expandable card class="margin-bottom-2">
        <template #header="{ toggle, expanded }">
          <div class="flex flex-100 justify-content-space-between">
            <a @click="toggle">
              {{ $t('googleForm.connectHeading') }}
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
            <li>{{ $t('googleForm.connectStep1') }}</li>
            <li>{{ $t('googleForm.connectStep2') }}</li>
            <li>{{ $t('googleForm.connectStep3') }}</li>
          </ol>
        </template>
      </Expandable>
    </FormGroup>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import oauth2IntegrationForm from '@baserow/modules/integrations/oauth2/oauth2IntegrationForm'
import OAuth2ConnectSection from '@baserow/modules/integrations/oauth2/components/integrations/OAuth2ConnectSection'
import OAuth2CredentialsFields from '@baserow/modules/integrations/oauth2/components/integrations/OAuth2CredentialsFields'

export default {
  name: 'GoogleForm',
  components: { OAuth2ConnectSection, OAuth2CredentialsFields },
  mixins: [oauth2IntegrationForm],
  setup() {
    return { v$: useVuelidate() }
  },
}
</script>
