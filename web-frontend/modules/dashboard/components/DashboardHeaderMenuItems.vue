<template>
  <div class="header__filter">
    <li class="header__filter-item">
      <a v-if="canEdit" class="header__filter-link" @click="toggleEditMode">
        <i class="header__filter-icon iconoir-edit"></i>
        <span class="header__filter-name">{{
          $t('dashboardHeaderMenuItems.editMode')
        }}</span>
      </a>
    </li>
  </div>
</template>

<script>
import { mapActions } from 'vuex'

export default {
  name: 'DashboardHeaderMenuItems',
  props: {
    dashboard: {
      type: Object,
      required: true,
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
    ...mapActions({
      toggleEditMode: 'dashboardApplication/toggleEditMode',
    }),
  },
}
</script>
