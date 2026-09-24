<template>
  <div class="create-widget-button">
    <CreateWidgetModal
      ref="createWidgetModal"
      :dashboard="dashboard"
      :loading="loading"
      @widget-variation-selected="$emit('widget-variation-selected', $event)"
    />
    <Button
      icon="iconoir-plus"
      type="secondary"
      :loading="loading"
      @click="openCreateWidgetModal"
      >{{ $t('dashboard.addWidget') }}</Button
    >
  </div>
</template>

<script>
import CreateWidgetModal from '@baserow/modules/dashboard/components/CreateWidgetModal'

export default {
  name: 'CreateWidgetButton',
  components: { CreateWidgetModal },
  props: {
    dashboard: {
      type: Object,
      required: true,
    },
    loading: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['widget-variation-selected'],
  methods: {
    openCreateWidgetModal() {
      if (this.loading) {
        return
      }

      this.$refs.createWidgetModal.show()
    },
  },
}
</script>
