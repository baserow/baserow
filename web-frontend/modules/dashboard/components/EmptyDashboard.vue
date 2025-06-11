<template>
  <div class="empty-dashboard">
    <div class="empty-dashboard__content">
      <div class="empty-dashboard__content-title">
        {{ $t('emptyDashboard.title') }}
      </div>
      <div v-if="canCreateWidget()" class="empty-dashboard__content-subtitle">
        {{ $t('emptyDashboard.subtitle') }}
      </div>
      <Button
        v-if="canCreateWidget()"
        type="primary"
        icon="iconoir-plus"
        @click="openCreateWidgetModal"
        >{{ $t('emptyDashboard.addWidget') }}</Button
      >
    </div>
    <CreateWidgetModal
      ref="createWidgetModal"
      :dashboard="dashboard"
      @widget-variation-selected="$emit('widget-variation-selected', $event)"
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
    canCreateWidget() {
      return this.$hasPermission(
        'dashboard.create_widget',
        this.dashboard,
        this.dashboard.workspace.id
      )
    },
  },
}
</script>
