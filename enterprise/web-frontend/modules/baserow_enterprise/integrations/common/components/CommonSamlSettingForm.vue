<template>
  <AuthProviderWithModal
    :auth-provider-type="authProviderType"
    :auth-provider="authProvider"
    :in-error="inError"
    @delete="$emit('delete')"
    @hidden="checkValidity()"
  >
    <SamlSettingsForm
      v-bind="$props"
      ref="form"
      @values-changed="checkValidity"
      v-on="$listeners"
    >
      <template #config>
        <FormGroup
          small-label
          required
          :label="$t('commonSamlSettingForm.relayStateTitle')"
          class="margin-bottom-2"
        >
          <div class="common-saml-setting-form__url-block">
            <div
              v-for="url in relayStateUrls"
              :key="url"
              class="common-saml-setting-form__url"
              @click.prevent=";[copyToClipboard(url), $refs.copiedRelay.show()]"
            >
              <span class="common-saml-setting-form__url-dest" :title="url">
                {{ url }}
              </span>
            </div>
            <div v-if="relayStateUrls.length === 0">
              {{ $t('commonSamlSettingForm.addDomainNotice') }}
            </div>
            <Copied ref="copiedRelay"></Copied>
          </div>
        </FormGroup>

        <FormGroup
          small-label
          required
          :label="$t('commonSamlSettingForm.acsTitle')"
          class="margin-bottom-2"
        >
          <div class="common-saml-setting-form__url-block">
            <div
              class="common-saml-setting-form__url"
              @click.prevent="
                ;[copyToClipboard(acsUrl), $refs.copiedACS.show()]
              "
            >
              <span class="common-saml-setting-form__url-dest" :title="acsUrl">
                {{ acsUrl }}
              </span>
            </div>
            <Copied ref="copiedACS"></Copied>
          </div>
        </FormGroup>
      </template>
    </SamlSettingsForm>
  </AuthProviderWithModal>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import SamlSettingsForm from '@baserow_enterprise/components/admin/forms/SamlSettingsForm'
import authProviderForm from '@baserow/modules/core/mixins/authProviderForm'
import AuthProviderWithModal from '@baserow/modules/builder/components/userSource/AuthProviderWithModal'
import { copyToClipboard } from '@baserow/modules/database/utils/clipboard'

export default {
  name: 'CommonSamlSettingsForm',
  components: { SamlSettingsForm, AuthProviderWithModal },
  mixins: [authProviderForm],
  props: {
    integration: {
      type: Object,
      required: true,
    },
    userSource: {
      type: Object,
      required: true,
    },
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return { inError: false, values: {} }
  },
  computed: {
    relayStateUrls() {
      return this.authProviderType.getRelayStateUrls(this.userSource)
    },
    acsUrl() {
      return this.authProviderType.getAcsUrl(this.userSource)
    },
  },
  watch: {
    'v$.$anyDirty'() {
      this.checkValidity()
    },
  },
  methods: {
    copyToClipboard,
    checkValidity() {
      if (!this.$refs.form.isFormValid() && this.$refs.form.v$.$anyDirty) {
        this.inError = true
      } else {
        this.inError = false
      }
    },
    handleServerError(error) {
      if (this.$refs.form.handleServerError(error)) {
        this.inError = true
        return true
      }
      return false
    },
  },
  validations() {
    return {}
  },
}
</script>
