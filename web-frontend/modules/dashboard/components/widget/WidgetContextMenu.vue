<template>
  <div class="widget-header__context-menu">
    <ButtonIcon
      icon="iconoir-more-vert"
      type="secondary"
      size="regular"
      @click.stop="
        $refs.context.toggle($event.target, 'bottom', 'right', 16, 8)
      "
    ></ButtonIcon>
    <WidgetContext
      ref="context"
      :widget="widget"
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
    widget: {
      type: Object,
      required: true,
    },
  },
}
</script>
