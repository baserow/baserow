<template>
  <div class="admin-settings__group">
    <h2 class="admin-settings__group-title">
      {{ $t('enterpriseSettings.branding') }}
    </h2>
    <div class="admin-settings__item">
      <div class="admin-settings__label">
        <div class="admin-settings__name">
          {{ $t('enterpriseSettings.showBaserowHelpMessage') }}
        </div>
        <div class="admin-settings__description">
          {{ $t('enterpriseSettings.showBaserowHelpMessageDescription') }}
        </div>
      </div>
      <div class="admin-settings__control">
        <SwitchInput
          v-tooltip="
            !$hasFeature(ENTERPRISE_SETTINGS)
              ? $t('enterpriseSettings.deactivated')
              : null
          "
          :value="
            $hasFeature(ENTERPRISE_SETTINGS)
              ? settings.show_baserow_help_request
              : true
          "
          :disabled="!$hasFeature(ENTERPRISE_SETTINGS)"
          @input="updateSettings({ show_baserow_help_request: $event })"
          >{{ $t('settings.enabled') }}</SwitchInput
        >
      </div>
    </div>
    <div class="admin-settings__item">
      <div class="admin-settings__label">
        <div class="admin-settings__name">
          {{ $t('enterpriseSettings.coBrandingLogo') }}
        </div>
        <div class="admin-settings__description">
          {{ $t('enterpriseSettings.coBrandingLogoDescription') }}
        </div>
      </div>
      <div class="admin-settings__control">
        <Button
          v-if="
            settings.co_branding_logo === null ||
            !$hasFeature(ENTERPRISE_SETTINGS)
          "
          v-tooltip="
            !$hasFeature(ENTERPRISE_SETTINGS)
              ? $t('enterpriseSettings.deactivated')
              : null
          "
          :disabled="!$hasFeature(ENTERPRISE_SETTINGS)"
          @click="$hasFeature(ENTERPRISE_SETTINGS) && openLogoUploadModal()"
        >
          {{ $t('enterpriseSettings.uploadFileButton') }}
        </Button>
        <Thumbnail
          v-else
          removable
          :src="settings.co_branding_logo.url"
          @remove="updateSettings({ co_branding_logo: null })"
        />
        <UserFilesModal
          ref="userFilesModal"
          :multiple-files="false"
          :file-types-acceptable="IMAGE_FILE_TYPES"
          @uploaded="fileUploaded"
        />
      </div>
    </div>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import { IMAGE_FILE_TYPES } from '@baserow/modules/core/enums'
import { notifyIf } from '@baserow/modules/core/utils/error'
import UserFilesModal from '@baserow/modules/core/components/files/UserFilesModal'
import { UploadFileUserFileUploadType } from '@baserow/modules/core/userFileUploadTypes'
import EnterpriseFeatures from '@baserow_enterprise/features'
import { useVuelidate } from '@vuelidate/core'

export default {
  name: 'EnterpriseSettings',
  components: { UserFilesModal },
  setup() {
    return {
      v$: useVuelidate({ $lazy: true }),
    }
  },
  computed: {
    IMAGE_FILE_TYPES() {
      return IMAGE_FILE_TYPES
    },
    ENTERPRISE_SETTINGS() {
      return EnterpriseFeatures.ENTERPRISE_SETTINGS
    },
    ...mapGetters({
      settings: 'settings/get',
    }),
  },
  methods: {
    async updateSettings(values) {
      this.v$.$touch()
      if (this.v$.$invalid) {
        return
      }
      try {
        await this.$store.dispatch('settings/update', values)
      } catch (error) {
        notifyIf(error, 'settings')
      }
    },
    openLogoUploadModal() {
      this.$refs.userFilesModal.show(UploadFileUserFileUploadType.getType())
    },
    fileUploaded([file]) {
      this.updateSettings({ co_branding_logo: file })
      this.$refs.userFilesModal.hide()
    },
  },
}
</script>
