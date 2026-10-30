<template>
  <header class="layout__col-2-1 header header--space-between">
    <SkeletonBlock
      v-if="loading"
      class="header__loading"
      width="140px"
      height="12px"
    ></SkeletonBlock>
    <template v-else>
      <div class="dashboard-app-header__mode">
        <Button
          v-if="isEditMode"
          type="primary"
          icon="iconoir-check"
          @click="doneEditing"
          >{{ $t('dashboardHeader.doneEditing') }}</Button
        >
        <DashboardHeaderMenuItems
          v-else
          :dashboard="dashboard"
          :store-prefix="storePrefix"
        />
      </div>
      <div class="dashboard-app-header__actions">
        <DashboardRefreshButton :store-prefix="storePrefix" />
        <CreateDashboardElementButton
          :dashboard="dashboard"
          :loading="isCreatingWidget || isCreatingFilter"
          @widget-variation-selected="
            $emit('widget-variation-selected', $event)
          "
          @create-filter="$emit('create-filter')"
        />
      </div>
    </template>
  </header>
</template>

<script>
import DashboardHeaderMenuItems from '@baserow/modules/dashboard/components/DashboardHeaderMenuItems'
import CreateDashboardElementButton from '@baserow/modules/dashboard/components/CreateDashboardElementButton'
import DashboardRefreshButton from '@baserow/modules/dashboard/components/filter/DashboardRefreshButton'

export default {
  name: 'DashboardHeader',
  components: {
    DashboardRefreshButton,
    DashboardHeaderMenuItems,
    CreateDashboardElementButton,
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
    loading: {
      type: Boolean,
      required: true,
    },
    isCreatingWidget: {
      type: Boolean,
      required: false,
      default: false,
    },
    isCreatingFilter: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['widget-variation-selected', 'create-filter'],
  computed: {
    isEditMode() {
      return this.$store.getters[
        `${this.storePrefix}dashboardApplication/isEditMode`
      ]
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
