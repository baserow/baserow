<template>
  <div class="empty-dashboard-sidebar">
    <i class="iconoir-cursor-pointer empty-dashboard-sidebar__icon"></i>
    <div class="empty-dashboard-sidebar__title">
      {{ $t('emptyDashboardSidebar.title') }}
    </div>
    <div class="empty-dashboard-sidebar__message">
      {{ $t('emptyDashboardSidebar.message') }}
    </div>
  </div>
</template>

<script>
export default {
  name: 'EmptyDashboardSidebar',
}
</script>
