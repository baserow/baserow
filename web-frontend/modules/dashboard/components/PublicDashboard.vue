<template>
  <div class="public-dashboard">
    <div
      class="public-dashboard__content dashboard-app__content"
      :class="{ 'dashboard-app__content--with-widgets': !isEmpty }"
    >
      <div class="public-dashboard__main">
        <div class="dashboard-app__content-header">
          <div class="dashboard-app__content-header-main">
            <div class="dashboard-app__title">{{ dashboard.name }}</div>
            <div
              v-if="dashboard.description"
              class="dashboard-app__description"
            >
              {{ dashboard.description }}
            </div>
          </div>
        </div>
        <DashboardWidgetGridLoading v-if="loading" />
        <div v-else-if="isEmpty" class="public-dashboard__empty">
          {{ $t('publicDashboard.noWidgets') }}
        </div>
        <WidgetBoard v-else :dashboard="dashboard" />
      </div>
      <div
        v-if="dashboard.show_logo || showReportLink"
        class="public-dashboard__footer"
      >
        <template v-if="showReportLink">
          <a
            class="public-dashboard__report-abuse"
            href="#"
            @click.prevent="reportAbuseModal.show()"
          >
            {{ $t('publicDashboard.reportAbuse') }}
          </a>
          <ReportAbuseModal
            ref="reportAbuseModal"
            resource-type="dashboard"
            :identifier="publicSlug"
            :request-config="reportRequestConfig"
          ></ReportAbuseModal>
        </template>
        <ExternalLinkBaserowLogo v-if="dashboard.show_logo" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useStore } from 'vuex'
import ExternalLinkBaserowLogo from '@baserow/modules/core/components/ExternalLinkBaserowLogo'
import ReportAbuseModal from '@baserow/modules/core/components/abuseReport/ReportAbuseModal'
import DashboardWidgetGridLoading from '@baserow/modules/dashboard/components/DashboardWidgetGridLoading'
import WidgetBoard from '@baserow/modules/dashboard/components/WidgetBoard'
import { PUBLIC_DASHBOARD_AUTHORIZATION_HEADER } from '@baserow/modules/dashboard/services/publicDashboard'

/**
 * Renders a publicly shared dashboard for its visitors: the name, the
 * description and the read-only widget grid. The widgets and their data live in
 * the `dashboardApplication` store, in its public mode.
 */
defineProps({
  dashboard: {
    type: Object,
    required: true,
  },
  loading: {
    type: Boolean,
    required: false,
    default: false,
  },
})

const store = useStore()
const reportAbuseModal = ref(null)

const isEmpty = computed(() => store.getters['dashboardApplication/isEmpty'])
const publicSlug = computed(
  () => store.getters['dashboardApplication/getPublicSlug']
)
// Visitors can report a shared dashboard for abuse, like a shared view, unless
// the instance admin switched reporting off.
const showReportLink = computed(
  () =>
    !!publicSlug.value &&
    store.getters['settings/get'].allow_reporting_abuse !== false
)
// A password protected dashboard can only be resolved with its access token.
const reportRequestConfig = computed(() => {
  const authToken = store.getters['dashboardApplication/getPublicAuthToken']
  return authToken
    ? {
        headers: {
          [PUBLIC_DASHBOARD_AUTHORIZATION_HEADER]: `JWT ${authToken}`,
        },
      }
    : {}
})
</script>
