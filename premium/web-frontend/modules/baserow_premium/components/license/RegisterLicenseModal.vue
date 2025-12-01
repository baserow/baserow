<template>
  <Modal>
    <h2 class="box__title">
      {{ $t('registerLicenseModal.titleRegisterLicense') }}
    </h2>
    <div>
      <i18n path="registerLicenseModal.licenseDescription" tag="p">
        <template #pricingLink>
          <a target="_blank" :href="viewPricingURL">{{
            $t('registerLicenseModal.viewPricing')
          }}</a>
        </template>
      </i18n>
      <p></p>
      <Error :error="error"></Error>
      <RegisterLicenseForm @submitted="submit">
        <div class="actions">
          <div class="align-right">
            <Button
              type="primary"
              size="large"
              :disabled="loading"
              :loading="loading"
            >
              {{ $t('registerLicenseModal.registerLicense') }}</Button
            >
          </div>
        </div>
      </RegisterLicenseForm>
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import LicenseService from '@baserow_premium/services/license'
import RegisterLicenseForm from '@baserow_premium/components/license/RegisterLicenseForm'
import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'
import {getPricingURL} from '@baserow_premium/utils/pricing'

export default {
  name: 'RegisterLicenseModal',
  components: { RegisterLicenseForm },
  mixins: [modal, error],
  props: {
    instanceId: {
      required: true,
      type: String,
    },
  },
  data() {
    return {
      loading: false,
    }
  },
  computed: {
    viewPricingURL() {
      return getPricingURL(this.instanceId)
    },
  },
  methods: {
    async submit(values) {
      this.hideError()
      this.loading = true

      try {
        const { data } = await LicenseService(this.$client).register(
          values.license
        )
        this.$emit('registered', data)
        await this.$nuxt.$router.push({
          name: 'admin-license',
          params: {
            id: data.id,
          },
        })
      } catch (error) {
        this.handleError(error, 'license', {
          ERROR_INVALID_LICENSE: new ResponseErrorMessage(
            this.$t('registerLicenseModal.licenseError.invalidTitle'),
            this.$t('registerLicenseModal.licenseError.invalid')
          ),
          ERROR_UNSUPPORTED_LICENSE: new ResponseErrorMessage(
            this.$t('registerLicenseModal.licenseError.unsupportedTitle'),
            this.$t('registerLicenseModal.licenseError.unsupported')
          ),
          ERROR_LICENSE_HAS_EXPIRED: new ResponseErrorMessage(
            this.$t('registerLicenseModal.licenseError.expiredTitle'),
            this.$t('registerLicenseModal.licenseError.expired')
          ),
          ERROR_LICENSE_ALREADY_EXISTS: new ResponseErrorMessage(
            this.$t('registerLicenseModal.licenseError.duplicateTitle'),
            this.$t('registerLicenseModal.licenseError.duplicate')
          ),
          ERROR_PREMIUM_LICENSE_INSTANCE_ID_MISMATCH: new ResponseErrorMessage(
            this.$t('registerLicenseModal.licenseError.instanceMismatchTitle'),
            this.$t('registerLicenseModal.licenseError.instanceMismatch')
          ),
        })
      }

      this.loading = false
    },
  },
}
</script>
