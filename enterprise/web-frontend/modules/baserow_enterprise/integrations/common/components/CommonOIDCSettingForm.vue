<template>
  <AuthProviderWithModal
    :auth-provider-type="authProviderType"
    :auth-provider="authProvider"
    :in-error="inError"
    @delete="$emit('delete')"
    @hidden="checkValidity()"
  >
    <OpenIdConnectSettingsForm
      v-bind="$props"
      ref="form"
      @values-changed="checkValidity"
      v-on="$listeners"
    >
      <template #config>
        <FormGroup
          small-label
          :label="$t('commonOidcSettingForm.callbackTitle')"
          required
          :helper-text="$t('commonOidcSettingForm.callbackHelperText')"
        >
          <div class="common-oidc-setting-form__url-block">
            <div
              v-for="callback in callbacks"
              :key="callback.name"
              class="common-oidc-setting-form__url"
            >
              <span class="common-oidc-setting-form__url-domain">
                {{ callback.name }}
              </span>
              <span
                class="common-oidc-setting-form__url-dest"
                :title="callback.url"
                @click.prevent="
                  ;[copyToClipboard(callback.url), $refs.copiedACS.show()]
                "
              >
                {{ callback.previewUrl }}
              </span>
            </div>
            <Copied ref="copiedACS"></Copied>
          </div>
        </FormGroup>
      </template>
    </OpenIdConnectSettingsForm>
  </AuthProviderWithModal>
</template>

<script>
import OpenIdConnectSettingsForm from '@baserow_enterprise/components/admin/forms/OpenIdConnectSettingsForm.vue'
import authProviderForm from '@baserow/modules/core/mixins/authProviderForm'
import AuthProviderWithModal from '@baserow/modules/builder/components/userSource/AuthProviderWithModal'
import { mapGetters } from 'vuex'
import { copyToClipboard } from '@baserow/modules/database/utils/clipboard'

export default {
  name: 'CommonOIDCSettingsForm',
  components: { OpenIdConnectSettingsForm, AuthProviderWithModal },
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
  data() {
    return { inError: false, values: {} }
  },
  computed: {
    ...mapGetters({ domains: 'domain/getDomains' }),
    callbacks() {
      const userSourceType = this.$registry.get(
        'userSource',
        this.userSource.type
      )

      const userSourceUid = userSourceType.genUid(this.userSource)

      const url = `${this.$config.PUBLIC_BACKEND_URL}/api/user-source/${userSourceUid}/sso/oauth2/openid_connect/callback/`
      const previewUrl = `${this.$config.PUBLIC_BACKEND_URL.substr(
        0,
        10
      )}.../user-source/${userSourceUid}/sso/...`

      const preview = [
        {
          name: this.$t('commonOidcSettingForm.preview'),
          url,
          previewUrl,
        },
      ]

      const others = this.domains.map((domain) => ({
        name: domain.domain_name,
        url: `${this.$config.PUBLIC_BACKEND_URL}/api/user-source/domain_${domain.id}__${userSourceUid}/sso/oauth2/openid_connect/callback/`,
        previewUrl: `${this.$config.PUBLIC_BACKEND_URL.substr(
          0,
          10
        )}.../user-source/domain_${domain.id}__${userSourceUid}/sso/...`,
      }))

      return [...preview, ...others]
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
