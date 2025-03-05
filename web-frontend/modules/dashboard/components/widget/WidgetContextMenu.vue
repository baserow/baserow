<template>
  <div ref="contextButton" class="widget__header-context-menu">
    <ButtonIcon
      icon="iconoir-more-vert"
      type="secondary"
      size="regular"
      @click.stop="
        $refs.context.toggle($refs.contextButton, 'bottom', 'right', 8, -8)
      "
    ></ButtonIcon>
    <WidgetContext
      ref="context"
      :widget="widget"
      :dashboard="dashboard"
      @delete-widget="$emit('delete-widget', $event)"
    ></WidgetContext>
  </div>
</template>

<script>
import WidgetContext from '@baserow/modules/dashboard/components/widget/WidgetContext'

export default {
  name: 'WidgetContextMenu',
  components: { WidgetContext },
  props: {
    dashboard: {
      type: Object,
      required: true,
    },
    widget: {
      type: Object,
      required: true,
    },
  },
}
</script>
