<template>
  <div class="header__filter">
    <li v-if="canEdit" class="header__filter-item">
      <Button type="secondary" icon="iconoir-edit" @click="toggleEditMode">{{
        $t('dashboardHeaderMenuItems.editMode')
      }}</Button>
    </li>
    <li v-if="canEdit" class="header__filter-item">
      <ShareDashboardLink :dashboard="dashboard" />
    </li>
  </div>
</template>

<script>
import ShareDashboardLink from '@baserow/modules/dashboard/components/sharing/ShareDashboardLink'

export default {
  name: 'DashboardHeaderMenuItems',
  components: { ShareDashboardLink },
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
  },
  computed: {
    canEdit() {
      return this.$hasPermission(
        'application.update',
        this.dashboard,
        this.dashboard.workspace.id
      )
    },
  },
  methods: {
    toggleEditMode() {
      this.$store.dispatch(
        this.storePrefix + `dashboardApplication/toggleEditMode`
      )
    },
  },
}
</script>
