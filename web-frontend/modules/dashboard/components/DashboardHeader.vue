<template>
  <header class="layout__col-2-1 header header--space-between">
    <SkeletonBlock
      v-if="loading"
      class="header__loading"
      width="140px"
      height="12px"
    ></SkeletonBlock>
    <template v-else>
      <DashboardHeaderMenuItems
        v-if="!isEditMode"
        :dashboard="dashboard"
        :store-prefix="storePrefix"
      />
      <div v-else class="dashboard-app-header__done-editing">
        <Button type="primary" @click="doneEditing">{{
          $t('dashboardHeader.doneEditing')
        }}</Button>
      </div>
    </template>
  </header>
</template>

<script>
import DashboardHeaderMenuItems from '@baserow/modules/dashboard/components/DashboardHeaderMenuItems'

export default {
  name: 'DashboardHeader',
  components: {
    DashboardHeaderMenuItems,
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
  },
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
