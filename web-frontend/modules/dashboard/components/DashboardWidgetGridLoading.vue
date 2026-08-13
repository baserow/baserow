<template>
  <div
    class="dashboard-widget-grid__loading loading-spinner"
    data-testid="dashboard-widget-grid-loading"
    role="status"
    :aria-label="$t('dashboard.widgetsLoading')"
  ></div>
</template>

<script>
export default {
  name: 'DashboardWidgetGridLoading',
}
</script>
