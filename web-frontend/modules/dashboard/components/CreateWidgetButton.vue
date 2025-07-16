<template>
  <div class="create-widget-button">
    <CreateWidgetModal
      ref="createWidgetModal"
      :dashboard="dashboard"
      @widget-variation-selected="$emit('widget-variation-selected', $event)"
    />
    <ButtonFloating
      icon="iconoir-plus"
      type="secondary"
      @click="openCreateWidgetModal"
    ></ButtonFloating>
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
  },
  methods: {
    openCreateWidgetModal() {
      this.$refs.createWidgetModal.show()
    },
  },
}
</script>
