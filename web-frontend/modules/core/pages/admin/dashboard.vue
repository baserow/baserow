<template>
  <div class="layout__col-2-scroll">
    <div class="admin-dashboard">
      <h1>{{ $t('adminDashboard.title') }}</h1>
      <div class="row margin-bottom-3">
        <div class="col col-4">
          <div class="admin-dashboard__box">
            <div v-if="loading" class="loading-overlay"></div>
            <div class="admin-dashboard__box-title">
              {{ $t('adminDashboard.totals') }}
            </div>
            <div class="admin-dashboard__numbers">
              <div class="admin-dashboard__numbers-name">
                {{ $t('adminDashboard.totalUsers') }}
              </div>
              <div class="admin-dashboard__numbers-value">
                {{ data.total_users }}
              </div>
              <div class="admin-dashboard__numbers-percentage">
                <nuxt-link :to="{ name: 'admin-users' }">{{
                  $t('adminDashboard.viewAll')
                }}</nuxt-link>
              </div>
            </div>
            <div class="admin-dashboard__numbers">
              <div class="admin-dashboard__numbers-name">
                {{ $t('adminDashboard.totalWorkspaces') }}
              </div>
              <div class="admin-dashboard__numbers-value">
                {{ data.total_workspaces }}
              </div>
              <div class="admin-dashboard__numbers-percentage">
                <nuxt-link :to="{ name: 'admin-workspaces' }">{{
                  $t('adminDashboard.viewAll')
                }}</nuxt-link>
              </div>
            </div>
            <div class="admin-dashboard__numbers">
              <div class="admin-dashboard__numbers-name">
                {{ $t('adminDashboard.totalApplications') }}
              </div>
              <div class="admin-dashboard__numbers-value">
                {{ data.total_applications }}
              </div>
            </div>
          </div>
        </div>
        <div class="col col-4">
          <div class="admin-dashboard__box">
            <div v-if="loading" class="loading-overlay"></div>
            <div class="admin-dashboard__box-title">
              {{ $t('adminDashboard.newUsers') }}
            </div>
            <div class="admin-dashboard__numbers">
              <div class="admin-dashboard__numbers-name">
                {{ $t('adminDashboard.newUsers24h') }}
              </div>
              <div class="admin-dashboard__numbers-value">
                {{ data.new_users_last_24_hours }}
              </div>
              <div class="admin-dashboard__numbers-percentage">
                <span
                  class="admin-dashboard__numbers-percentage-value"
                  :class="{
                    'admin-dashboard__numbers-percentage-value--negative':
                      isNegative(percentages.new_users_last_24_hours),
                  }"
                  >{{ percentages.new_users_last_24_hours }}</span
                >
              </div>
            </div>
            <div class="admin-dashboard__numbers">
              <div class="admin-dashboard__numbers-name">
                {{ $t('adminDashboard.newUsers7days') }}
              </div>
              <div class="admin-dashboard__numbers-value">
                {{ data.new_users_last_7_days }}
              </div>
              <div class="admin-dashboard__numbers-percentage">
                <span
                  class="admin-dashboard__numbers-percentage-value"
                  :class="{
                    'admin-dashboard__numbers-percentage-value--negative':
                      isNegative(percentages.new_users_last_7_days),
                  }"
                  >{{ percentages.new_users_last_7_days }}</span
                >
              </div>
            </div>
            <div class="admin-dashboard__numbers">
              <div class="admin-dashboard__numbers-name">
                {{ $t('adminDashboard.newUsers30days') }}
              </div>
              <div class="admin-dashboard__numbers-value">
                {{ data.new_users_last_30_days }}
              </div>
              <div class="admin-dashboard__numbers-percentage">
                <span
                  class="admin-dashboard__numbers-percentage-value"
                  :class="{
                    'admin-dashboard__numbers-percentage-value--negative':
                      isNegative(percentages.new_users_last_30_days),
                  }"
                  >{{ percentages.new_users_last_30_days }}</span
                >
              </div>
            </div>
          </div>
        </div>
        <div class="col col-4">
          <div class="admin-dashboard__box">
            <div v-if="loading" class="loading-overlay"></div>
            <div class="admin-dashboard__box-title">
              {{ $t('adminDashboard.activeUsers') }}
            </div>
            <div class="admin-dashboard__numbers">
              <div class="admin-dashboard__numbers-name">
                {{ $t('adminDashboard.activeUsers24h') }}
              </div>
              <div class="admin-dashboard__numbers-value">
                {{ data.active_users_last_24_hours }}
              </div>
              <div class="admin-dashboard__numbers-percentage">
                <span
                  class="admin-dashboard__numbers-percentage-value"
                  :class="{
                    'admin-dashboard__numbers-percentage-value--negative':
                      isNegative(percentages.new_users_last_30_days),
                  }"
                  >{{ percentages.active_users_last_24_hours }}</span
                >
              </div>
            </div>
            <div class="admin-dashboard__numbers">
              <div class="admin-dashboard__numbers-name">
                {{ $t('adminDashboard.activeUsers7days') }}
              </div>
              <div class="admin-dashboard__numbers-value">
                {{ data.active_users_last_7_days }}
              </div>
              <div class="admin-dashboard__numbers-percentage">
                <span
                  class="admin-dashboard__numbers-percentage-value"
                  :class="{
                    'admin-dashboard__numbers-percentage-value--negative':
                      isNegative(percentages.active_users_last_7_days),
                  }"
                  >{{ percentages.active_users_last_7_days }}</span
                >
              </div>
            </div>
            <div class="admin-dashboard__numbers">
              <div class="admin-dashboard__numbers-name">
                {{ $t('adminDashboard.activeUsers30days') }}
              </div>
              <div class="admin-dashboard__numbers-value">
                {{ data.active_users_last_30_days }}
              </div>
              <div class="admin-dashboard__numbers-percentage">
                <span
                  class="admin-dashboard__numbers-percentage-value"
                  :class="{
                    'admin-dashboard__numbers-percentage-value--negative':
                      isNegative(percentages.active_users_last_30_days),
                  }"
                  >{{ percentages.active_users_last_30_days }}</span
                >
              </div>
            </div>
          </div>
        </div>
      </div>
      <div class="admin-dashboard__box">
        <div v-if="loading" class="loading-overlay"></div>
        <ActiveUsers
          :new-users="data.new_users_per_day"
          :active-users="data.active_users_per_day"
        ></ActiveUsers>
      </div>
    </div>
  </div>
</template>

<script>
import { notifyIf } from '@baserow/modules/core/utils/error'

import ActiveUsers from '@baserow/modules/core/components/admin/dashboard/charts/ActiveUsers'
import AdminDashboardService from '@baserow/modules/core/services/admin/dashboard'

export default {
  components: { ActiveUsers },
  layout: 'app',
  middleware: 'staff',
  data() {
    return {
      loading: true,
      data: {
        total_users: 0,
        total_workspaces: 0,
        total_applications: 0,
        new_users_last_24_hours: 0,
        new_users_last_7_days: 0,
        new_users_last_30_days: 0,
        active_users_last_24_hours: 0,
        active_users_last_7_days: 0,
        active_users_last_30_days: 0,
        previous_new_users_last_24_hours: 0,
        previous_new_users_last_7_days: 0,
        previous_new_users_last_30_days: 0,
        previous_active_users_last_24_hours: 0,
        previous_active_users_last_7_days: 0,
        previous_active_users_last_30_days: 0,
        new_users_per_day: [],
        active_users_per_day: [],
      },
    }
  },
  computed: {
    percentages() {
      const percentage = (value1, value2) => {
        if (value1 === 0 || value2 === 0) {
          return ''
        }

        let value = value1 / value2 - 1
        value = Math.round(value * 100 * 100) / 100
        value = `${value > 0 ? '+ ' : '- '}${Math.abs(value)}%`
        return value
      }
      return {
        new_users_last_24_hours: percentage(
          this.data.new_users_last_24_hours,
          this.data.previous_new_users_last_24_hours
        ),
        new_users_last_7_days: percentage(
          this.data.new_users_last_7_days,
          this.data.previous_new_users_last_7_days
        ),
        new_users_last_30_days: percentage(
          this.data.new_users_last_30_days,
          this.data.previous_new_users_last_30_days
        ),
        active_users_last_24_hours: percentage(
          this.data.active_users_last_24_hours,
          this.data.previous_active_users_last_24_hours
        ),
        active_users_last_7_days: percentage(
          this.data.active_users_last_7_days,
          this.data.previous_active_users_last_7_days
        ),
        active_users_last_30_days: percentage(
          this.data.active_users_last_30_days,
          this.data.previous_active_users_last_30_days
        ),
      }
    },
  },
  /**
   * Because the results depend on the timezone of the user, we can only fetch the data
   * on the client side. Therefore, this part is not included in the asyncData.
   */
  async mounted() {
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone

    try {
      const { data } = await AdminDashboardService(this.$client).dashboard(
        timezone
      )
      this.data = data
    } catch (error) {
      notifyIf(error)
    }

    this.loading = false
  },
  methods: {
    isNegative(value) {
      return value.substr(0, 1) === '-'
    },
  },
}
</script>
