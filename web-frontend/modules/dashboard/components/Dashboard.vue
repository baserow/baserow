<template>
  <div class="dashboard-app">
    <DashboardHeader
      :dashboard="dashboard"
      :store-prefix="storePrefix"
      :loading="loading"
    />
    <DashboardContent
      :dashboard="dashboard"
      :store-prefix="storePrefix"
      :loading="loading"
    />
  </div>
</template>

<script>
import DashboardHeader from '@baserow/modules/dashboard/components/DashboardHeader'
import DashboardContent from '@baserow/modules/dashboard/components/DashboardContent'

export default {
  name: 'Dashboard',
  components: { DashboardHeader, DashboardContent },
  props: {
    dashboard: {
      type: Object,
      required: true,
    },
    storePrefix: {
      type: String,
      required: false,
      default: '',
    },
    loading: {
      type: Boolean,
      required: true,
    },
  },
}
</script>
