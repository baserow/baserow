<template>
  <div class="empty-dashboard">
    <div class="empty-dashboard__content">
      <div class="empty-dashboard__content-title">
        {{ $t('emptyDashboard.title') }}
      </div>
      <div class="empty-dashboard__content-subtitle">
        {{ $t('emptyDashboard.subtitle') }}
      </div>
      <Button
        type="primary"
        icon="iconoir-plus"
        @click="openCreateWidgetModal"
        >{{ $t('emptyDashboard.addWidget') }}</Button
      >
    </div>
    <CreateWidgetModal
      ref="createWidgetModal"
      :dashboard="dashboard"
      @widget-type-selected="$emit('widget-type-selected', $event)"
    />
  </div>
</template>

<script>
import CreateWidgetModal from '@baserow/modules/dashboard/components/CreateWidgetModal'

export default {
  name: 'EmptyDashboard',
  components: { CreateWidgetModal },
  props: {
    dashboard: {
      type: Object,
      required: true,
    },
  },
  methods: {
    openCreateWidgetModal() {
      this.$refs.createWidgetModal.show()
    },
  },
}
</script>
