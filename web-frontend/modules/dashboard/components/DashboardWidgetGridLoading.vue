<template>
  <div
    class="dashboard-widget-grid__loading"
    data-testid="dashboard-widget-grid-loading"
    role="status"
  >
    <span
      class="dashboard-widget-grid__loading-spinner"
      aria-hidden="true"
    ></span>
    <span class="dashboard-widget-grid__loading-label">
      {{ $t('dashboard.widgetsLoading') }}
    </span>
  </div>
</template>

<script>
export default {
  name: 'DashboardWidgetGridLoading',
}
</script>
