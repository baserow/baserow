<template>
  <Context ref="context" overflow-scroll max-height-if-outside-viewport>
    <ul class="context__menu">
      <li v-if="canBeDeleted" class="context__menu-item">
        <a
          class="context__menu-item-link context__menu-item-link--delete"
          @click="
            hide()
            $emit('delete-widget', widget.id)
          "
        >
          <i class="context__menu-item-icon iconoir-bin"></i>
          {{ $t('widgetContext.delete') }}
        </a>
      </li>
    </ul>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'

export default {
  name: 'WidgetContext',
  mixins: [context],
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
  computed: {
    canBeDeleted() {
      return this.$hasPermission(
        'dashboard.widget.delete',
        this.widget,
        this.dashboard.workspace.id
      )
    },
  },
}
</script>
