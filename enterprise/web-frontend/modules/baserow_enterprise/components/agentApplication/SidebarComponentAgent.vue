<template>
  <div class="agent-sidebar">
    <SidebarApplication
      ref="sidebarApplication"
      :workspace="workspace"
      :application="application"
      :highlighted="isAppSelected(application)"
      @selected="selected"
    >
      <template v-if="isAppSelected(application)" #body></template>
    </SidebarApplication>
    <BadgeCounter
      v-if="pendingApprovalsCount > 0"
      class="agent-sidebar__pending-approvals"
      :count="pendingApprovalsCount"
      :limit="100"
      :title="
        $t('agentSidebar.pendingApprovals', { count: pendingApprovalsCount })
      "
    ></BadgeCounter>
  </div>
</template>

<script>
import SidebarApplication from '@baserow/modules/core/components/sidebar/SidebarApplication'
import BadgeCounter from '@baserow/modules/core/components/BadgeCounter'
import { mapGetters } from 'vuex'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { pageFinished } from '@baserow/modules/core/utils/routing'
import { nextTick, useNuxtApp } from '#imports'

export default {
  name: 'SidebarComponentAgent',
  components: {
    SidebarApplication,
    BadgeCounter,
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
  setup() {
    const nuxtApp = useNuxtApp()
    return { nuxtApp }
  },
  computed: {
    ...mapGetters({
      isAppSelected: 'application/isSelected',
    }),
    pendingApprovalsCount() {
      return this.application.pending_approvals_count || 0
    },
  },
  methods: {
    async selected(application) {
      try {
        this.$store.dispatch('application/select', application)
        await this.$router.push({
          name: 'agent-application',
          params: {
            agentApplicationId: this.application.id,
          },
        })
        await pageFinished(this.nuxtApp)
        await nextTick()
      } catch (error) {
        if (error.name !== 'NavigationDuplicated') {
          notifyIf(error, 'workspace')
        }
      }
    },
  },
}
</script>
