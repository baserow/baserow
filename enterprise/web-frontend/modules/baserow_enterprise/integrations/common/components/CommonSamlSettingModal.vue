<template>
  <Modal ref="modal" keep-content @hidden="onHide">
    <h2 class="box__title">{{ $t('commonSamlSettingModal.title') }}</h2>
    <div>
      <SamlSettingsForm
        v-bind="$props"
        ref="samlForm"
        @values-changed="checkValidity"
        v-on="$listeners"
      >
        <template #config>
          <FormGroup
            small-label
            required
            :label="$t('commonSamlSettingModal.relayStateTitle')"
            class="margin-bottom-2"
          >
            <div class="common-saml-setting-modal__url-block">
              <div
                v-for="conf in config"
                :key="conf.name"
                class="common-saml-setting-modal__url"
                @click.prevent="
                  ;[copyToClipboard(conf.relay), $refs.copiedRelay.show()]
                "
              >
                <span class="common-saml-setting-modal__url-domain">
                  {{ conf.name }}
                </span>
                <span
                  class="common-saml-setting-modal__url-dest"
                  :title="conf.relay"
                >
                  {{ conf.relay }}
                </span>
              </div>
              <Copied ref="copiedRelay"></Copied>
            </div>
          </FormGroup>

          <FormGroup
            small-label
            required
            :label="$t('commonSamlSettingModal.acsTitle')"
            class="margin-bottom-2"
          >
            <div class="common-saml-setting-modal__url-block">
              <div
                v-for="conf in config"
                :key="conf.name"
                class="common-saml-setting-modal__url"
                @click.prevent="
                  ;[copyToClipboard(conf.acs), $refs.copiedACS.show()]
                "
              >
                <span class="common-saml-setting-modal__url-domain">
                  {{ conf.name }}
                </span>
                <span
                  class="common-saml-setting-modal__url-dest"
                  :title="conf.acs"
                >
                  {{ conf.acs }}
                </span>
              </div>
              <Copied ref="copiedACS"></Copied>
            </div>
          </FormGroup>
        </template>
      </SamlSettingsForm>
      <div class="actions actions--right">
        <Button size="large" @click.prevent="$refs.modal.hide()">
          {{ $t('action.close') }}
        </Button>
      </div>
    </div>
  </Modal>
</template>

<script>
import SamlSettingsForm from '@baserow_enterprise/components/admin/forms/SamlSettingsForm'
import authProviderForm from '@baserow/modules/core/mixins/authProviderForm'
import error from '@baserow/modules/core/mixins/error'
import { copyToClipboard } from '@baserow/modules/database/utils/clipboard'
import { mapActions, mapGetters } from 'vuex'
import modal from '@baserow/modules/core/mixins/modal'

export default {
  name: 'CommonSamlSettingsModal',
  components: { SamlSettingsForm },
  mixins: [error, authProviderForm, modal],
  inject: ['builder'],
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
  async fetch() {
    try {
      await this.actionFetchDomains({ builderId: this.builder.id })
    } catch (error) {
      this.handleError(error)
    }
  },
  computed: {
    ...mapGetters({ domains: 'domain/getDomains' }),
    config() {
      const previewRelay = `${this.$config.PUBLIC_WEB_FRONTEND_URL}/builder/${this.builder.id}/preview/`
      const previewACS = `${this.$config.PUBLIC_BACKEND_URL}/api/user-source/${this.userSource.uid}/sso/saml/acs/`
      const preview = [
        {
          name: this.$t('commonSamlSettingModal.preview'),
          acs: previewACS,
          relay: previewRelay,
        },
      ]

      const others = this.domains.map((domain) => ({
        name: domain.domain_name,
        acs: `${this.$config.PUBLIC_BACKEND_URL}/api/user-source/domain_${domain.id}__${this.userSource.uid}/sso/saml/acs/`,
        relay: this.getDomainUrl(domain),
      }))
      return [...preview, ...others]
    },
  },
  watch: {
    '$v.$anyDirty'() {
      // Force validity refresh on child touch
      this.checkValidity()
    },
  },
  methods: {
    ...mapActions({
      actionFetchDomains: 'domain/fetch',
    }),
    copyToClipboard(value) {
      copyToClipboard(value)
    },
    onHide() {
      this.checkValidity()
    },
    checkValidity() {
      if (
        !this.$refs.samlForm.isFormValid() &&
        this.$refs.samlForm.$v.$anyDirty
      ) {
        this.$emit('form-valid', false)
      } else {
        this.$emit('form-valid', true)
      }
    },
    getDomainUrl(domain) {
      const url = new URL(this.$config.PUBLIC_WEB_FRONTEND_URL)
      return `${url.protocol}//${domain.domain_name}${
        url.port ? `:${url.port}` : ''
      }`
    },
    handleServerError(error) {
      return this.$refs.samlForm.handleServerError(error)
    },
  },
  validations() {
    // Keep this to get the `$v` property
    return {}
  },
}
</script>
