<template>
  <header class="layout__col-2-1 header header--space-between">
    <div v-show="isLoading" class="header__loading"></div>
    <template v-if="!isLoading">
      <DashboardHeaderMenuItems v-if="!isEditMode" :dashboard="dashboard" />
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
import { mapGetters } from 'vuex'

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
  },
  computed: {
    ...mapGetters({
      isEditMode: 'dashboardApplication/isEditMode',
      isLoading: 'dashboardApplication/isLoading',
    }),
  },
  methods: {
    doneEditing() {
      this.$store.dispatch('dashboardApplication/toggleEditMode')
    },
  },
}
</script>
