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
                v-for="url in relayStateUrls"
                :key="url"
                class="common-saml-setting-modal__url"
                @click.prevent="
                  ;[copyToClipboard(url), $refs.copiedRelay.show()]
                "
              >
                <span class="common-saml-setting-modal__url-dest" :title="url">
                  {{ url }}
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
                class="common-saml-setting-modal__url"
                @click.prevent="
                  ;[copyToClipboard(acsUrl), $refs.copiedACS.show()]
                "
              >
                <span
                  class="common-saml-setting-modal__url-dest"
                  :title="acsUrl"
                >
                  {{ acsUrl }}
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
import modal from '@baserow/modules/core/mixins/modal'

export default {
  name: 'CommonSamlSettingsModal',
  components: { SamlSettingsForm },
  mixins: [error, authProviderForm, modal],
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
  computed: {
    relayStateUrls() {
      return this.authProviderType.getRelayStateUrls(this.userSource)
    },
    acsUrl() {
      return this.authProviderType.getAcsUrl(this.userSource)
    },
  },
  watch: {
    '$v.$anyDirty'() {
      // Force validity refresh on child touch
      this.checkValidity()
    },
  },
  methods: {
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
