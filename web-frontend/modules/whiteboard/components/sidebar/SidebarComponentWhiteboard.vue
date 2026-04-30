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
import { pageFinished } from '@baserow/modules/core/utils/routing'
import { nextTick, useNuxtApp } from '#imports'

export default {
  name: 'SidebarComponentWhiteboard',
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
  setup() {
    const nuxtApp = useNuxtApp()
    return { nuxtApp }
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
        await this.$router.push({
          name: 'whiteboard-application',
          params: {
            whiteboardId: this.application.id,
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
