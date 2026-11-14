<template>
  <div>
    <slot></slot>
    <div class="made-with-baserow">
      <a
        class="made-with-baserow__link"
        title="Open source self-hosted no-code platform"
        :href="showPaidFeaturesModal ? null : 'https://baserow.io/'"
        :target="showPaidFeaturesModal ? null : '_blank'"
        @click="handleMadeWithBaserowClick"
      >
        Made with
        <img
          src="@baserow_enterprise/assets/images/builder/mini_logo.svg?url"
          alt="Baserow"
        />
      </a>
      <a
        v-if="showReportLink"
        class="made-with-baserow__link made-with-baserow__report-abuse"
        href="#"
        @click.prevent="$refs.reportAbuseModal.show()"
      >
        {{ $t('madeWithBaserow.reportAbuse') }}
      </a>
    </div>

    <ReportAbuseModal
      v-if="showReportLink"
      ref="reportAbuseModal"
      resource-type="builder"
      :identifier="publicDomain"
    ></ReportAbuseModal>
    <PaidFeaturesModal
      ref="paidFeaturesModal"
      :initial-selected-type="paidFeatureType"
    ></PaidFeaturesModal>
  </div>
</template>

<script>
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import ReportAbuseModal from '@baserow/modules/core/components/abuseReport/ReportAbuseModal'
import { BuilderBrandingPaidFeature } from '@baserow_enterprise/paidFeatures'

export default {
  components: {
    PaidFeaturesModal,
    ReportAbuseModal,
  },
  props: {
    showPaidFeaturesModal: {
      type: Boolean,
      default: false,
    },
  },
  computed: {
    paidFeatureType() {
      return BuilderBrandingPaidFeature.getType()
    },
    /**
     * The domain the published application is visited on. It identifies the
     * application in an abuse report, and it's only set on the published site,
     * not in the editor or in preview mode.
     */
    publicDomain() {
      return this.showPaidFeaturesModal
        ? null
        : this.$store.getters['publicBuilder/getPublicDomain']
    },
    showReportLink() {
      return (
        !!this.publicDomain &&
        this.$store.getters['settings/isLoaded'] &&
        this.$store.getters['settings/get'].allow_reporting_abuse !== false
      )
    },
  },
  serverPrefetch() {
    // Loaded during server side rendering so that the report link is part of the
    // first render instead of appearing once the page is hydrated.
    return this.loadSettings()
  },
  mounted() {
    // Fallback for when the badge is first rendered in the browser.
    this.loadSettings()
  },
  methods: {
    /**
     * Published applications don't load the instance settings, but they tell
     * whether reporting is allowed and configure the captcha of the report form.
     * They're only loaded for the applications that show the badge.
     */
    async loadSettings() {
      if (this.publicDomain && !this.$store.getters['settings/isLoaded']) {
        try {
          await this.$store.dispatch('settings/load')
        } catch {
          // Without the settings the badge simply doesn't show the report link.
        }
      }
    },
    handleMadeWithBaserowClick(event) {
      if (this.showPaidFeaturesModal) {
        event.preventDefault()
        this.$refs.paidFeaturesModal.show()
      }
    },
  },
}
</script>
