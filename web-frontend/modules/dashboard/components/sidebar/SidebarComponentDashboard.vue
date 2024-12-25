<template>
  <div>
    <SidebarApplication
      ref="sidebarApplication"
      :workspace="workspace"
      :application="application"
      :highlighted="isAppSelected(application)"
      @selected="selected"
    >
      <template v-if="isAppSelected(application)" #body></template>
    </SidebarApplication>
  </div>
</template>

<script>
import SidebarApplication from '@baserow/modules/core/components/sidebar/SidebarApplication'
import { mapGetters } from 'vuex'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'SidebarComponentDashboard',
  components: {
    SidebarApplication,
  },
  props: {
    application: {
      type: Object,
      required: true,
    },
    workspace: {
      type: Object,
      required: true,
    },
  },
  computed: {
    ...mapGetters({
      isAppSelected: 'application/isSelected',
    }),
  },
  methods: {
    async selected(application) {
      try {
        this.$store.dispatch('application/select', application)
        await this.$nuxt.$router.push({
          name: 'dashboard-application',
          params: {
            dashboardId: this.application.id,
          },
        })
      } catch (error) {
        if (error.name !== 'NavigationDuplicated') {
          notifyIf(error, 'workspace')
        }
      }
    },
  },
}
</script>
