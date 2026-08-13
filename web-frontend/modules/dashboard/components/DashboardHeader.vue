<template>
  <header class="layout__col-2-1 header header--space-between">
    <div v-show="isLoading" class="header__loading"></div>
    <template v-if="!isLoading">
      <DashboardHeaderMenuItems
        v-if="!isEditMode"
        :dashboard="dashboard"
        :store-prefix="storePrefix"
      />
      <div v-else class="dashboard-app-header__done-editing">
        <Button type="primary" @click="doneEditing">{{
          $t('dashboardHeader.doneEditing')
        }}</Button>
        <CreateWidgetButton
          v-if="canCreateWidget"
          :dashboard="dashboard"
          :loading="isCreatingWidget"
          @widget-variation-selected="
            $emit('widget-variation-selected', $event)
          "
        />
      </div>
    </template>
  </header>
</template>

<script>
import DashboardHeaderMenuItems from '@baserow/modules/dashboard/components/DashboardHeaderMenuItems'
import CreateWidgetButton from '@baserow/modules/dashboard/components/CreateWidgetButton'

export default {
  name: 'DashboardHeader',
  components: {
    DashboardHeaderMenuItems,
    CreateWidgetButton,
  },
  props: {
    dashboard: {
      type: Object,
      required: true,
    },
    storePrefix: {
      type: String,
      required: false,
      default: '',
    },
    isCreatingWidget: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['widget-variation-selected'],
  computed: {
    isEditMode() {
      return this.$store.getters[
        `${this.storePrefix}dashboardApplication/isEditMode`
      ]
    },
    isLoading() {
      return this.$store.getters[
        `${this.storePrefix}dashboardApplication/isLoading`
      ]
    },
    canCreateWidget() {
      return this.$hasPermission(
        'dashboard.create_widget',
        this.dashboard,
        this.dashboard.workspace.id
      )
    },
  },
  methods: {
    doneEditing() {
      this.$store.dispatch(
        `${this.storePrefix}dashboardApplication/toggleEditMode`
      )
    },
  },
}
</script>
