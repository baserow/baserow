<template>
  <div v-if="showLogo || showReportLink" class="form-view__powered-by">
    <template v-if="showReportLink">
      <a
        class="form-view__report-abuse"
        href="#"
        @click.prevent="$refs.reportAbuseModal.show()"
      >
        {{ $t('formViewPoweredBy.reportAbuse') }}
      </a>
      <ReportAbuseModal
        ref="reportAbuseModal"
        resource-type="database_view"
        :identifier="$route.params.slug"
        :request-config="requestConfig"
      ></ReportAbuseModal>
    </template>
    <div v-if="showLogo" class="form-view__powered-by-baserow">
      Powered by
      <a
        href="https://baserow.io"
        target="_blank"
        title="Baserow - open source no-code database tool and Airtable alternative"
      >
        <Logo
          class="form-view__powered-by-logo"
          alt="Baserow - open source no-code database tool and Airtable alternative"
        />
      </a>
    </div>
  </div>
</template>

<script>
import ReportAbuseModal from '@baserow/modules/core/components/abuseReport/ReportAbuseModal'
import addPublicAuthTokenHeader from '@baserow/modules/database/utils/publicView'

export default {
  name: 'FormViewPoweredBy',
  components: { ReportAbuseModal },
  props: {
    showLogo: {
      type: Boolean,
      required: false,
      default: true,
    },
  },
  computed: {
    showReportLink() {
      // Only on the publicly shared form page, so that the link isn't shown in
      // the form editor preview, and even when the logo is hidden because
      // reporting must always be possible.
      return (
        this.$route.name === 'database-table-form' &&
        this.$store.getters['settings/get'].allow_reporting_abuse !== false
      )
    },
    requestConfig() {
      const publicAuthToken =
        this.$store.getters['page/view/public/getAuthToken']
      return publicAuthToken
        ? addPublicAuthTokenHeader({}, publicAuthToken)
        : {}
    },
  },
}
</script>
