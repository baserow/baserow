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
    </OpenIdConnectSettingsForm>
  </AuthProviderWithModal>
</template>

<script>
import OpenIdConnectSettingsForm from '@baserow_enterprise/components/admin/forms/OpenIdConnectSettingsForm.vue'
import authProviderForm from '@baserow/modules/core/mixins/authProviderForm'
import AuthProviderWithModal from '@baserow/modules/builder/components/userSource/AuthProviderWithModal'
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
    return { inError: false }
  },
  watch: {
    '$v.$anyDirty'() {
      this.checkValidity()
    },
  },
  methods: {
    copyToClipboard,
    checkValidity() {
      if (!this.$refs.form.isFormValid() && this.$refs.form.$v.$anyDirty) {
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
