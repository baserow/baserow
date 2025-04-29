<template>
  <div>
    <div
      v-tooltip="tooltipText"
      class="view-sharing__option"
      :class="{ 'view-sharing__option--disabled': !hasPremiumFeatures }"
      @click="click"
    >
      <SwitchInput
        small
        :value="!view.show_logo"
        :disabled="!hasPremiumFeatures"
        @input="update('show_logo', !$event)"
      >
        <img src="@baserow/modules/core/static/img/baserow-icon.svg" />
        <span>
          {{ $t('shareLinkOptions.baserowLogo.label') }}
        </span>
        <i v-if="!hasPremiumFeatures" class="deactivated-label iconoir-lock" />
      </SwitchInput>

      <PaidFeaturesModal
        v-if="!hasPremiumFeatures"
        ref="paidFeaturesModal"
        :workspace="workspace"
        initial-selected-type="public_logo_removal"
      ></PaidFeaturesModal>
    </div>
    <div
      v-if="hasValidExporter"
      v-tooltip="tooltipText"
      class="view-sharing__option"
      :class="{ 'view-sharing__option--disabled': !hasPremiumFeatures }"
      @click="click"
    >
      <SwitchInput
        small
        :value="view.allow_public_export"
        :disabled="!hasPremiumFeatures"
        @input="update('allow_public_export', $event)"
      >
        <i class="iconoir iconoir-share-ios"></i>
        <span>
          {{ $t('shareLinkOptions.allowPublicExportLabel') }}
        </span>
        <i v-if="!hasPremiumFeatures" class="deactivated-label iconoir-lock" />
      </SwitchInput>
    </div>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import ViewPremiumService from '@baserow_premium/services/view'
import { notifyIf } from '@baserow/modules/core/utils/error'
import PremiumFeatures from '@baserow_premium/features'
import viewTypeHasExporterTypes from '@baserow/modules/database/utils/viewTypeHasExporterTypes'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'

export default {
  name: 'PremiumViewOptions',
  components: { PaidFeaturesModal },

  props: {
    view: {
      type: Object,
      required: true,
    },
  },
  computed: {
    ...mapGetters({
      additionalUserData: 'auth/getAdditionalUserData',
    }),
    workspace() {
      return this.$store.getters['application/get'](this.view.table.database_id)
        .workspace
    },
    hasPremiumFeatures() {
      return this.$hasFeature(PremiumFeatures.PREMIUM, this.workspace.id)
    },
    tooltipText() {
      if (this.hasPremiumFeatures) {
        return null
      } else {
        return this.$t('premium.deactivated')
      }
    },
    hasValidExporter() {
      return viewTypeHasExporterTypes(this.view.type, this.$registry)
    },
  },
  methods: {
    async update(key, value) {
      try {
        // We are being optimistic that the request will succeed.
        this.$emit('update-view', { ...this.view, [key]: value })
        await ViewPremiumService(this.$client).update(this.view.id, {
          [key]: value,
        })
      } catch (error) {
        // In case it didn't we will roll back the change.
        this.$emit('update-view', { ...this.view, [key]: !value })
        notifyIf(error, 'view')
      }
    },
    click() {
      if (!this.hasPremiumFeatures) {
        this.$refs.paidFeaturesModal.show()
      }
    },
  },
}
</script>
