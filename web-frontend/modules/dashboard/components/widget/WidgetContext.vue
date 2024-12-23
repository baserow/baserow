<template>
  <Context ref="context" overflow-scroll max-height-if-outside-viewport>
    <ul class="context__menu">
      <li v-if="canBeDeleted" class="context__menu-item">
        <a
          class="context__menu-item-link context__menu-item-link--delete"
          :class="{ 'context__menu-item-link--loading': isDeleteInProgress }"
          @click="deleteWidget()"
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
import { notifyIf } from '@baserow/modules/core/utils/error'

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
  data() {
    return {
      isDeleteInProgress: false,
    }
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
  methods: {
    async deleteWidget() {
      this.isDeleteInProgress = true
      try {
        await this.$store.dispatch(
          'dashboardApplication/deleteWidget',
          this.widget.id
        )
      } catch (error) {
        notifyIf(error, 'dashboard')
      }
      this.isDeleteInProgress = false
      this.hide()
    },
  },
}
</script>
