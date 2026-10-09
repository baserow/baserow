<template>
  <Modal ref="modal" :left-sidebar="true">
    <template #sidebar>
      <ul class="modal-sidebar__nav">
        <li v-for="route in invitationRoutes" :key="route.type">
          <a
            class="modal-sidebar__nav-link"
            :class="{ active: route.type === activeRouteType }"
            @click="activeRouteType = route.type"
          >
            <i class="modal-sidebar__nav-icon" :class="route.iconClass"></i>
            {{ route.getName() }}
          </a>
        </li>
      </ul>
    </template>
    <template #content>
      <component
        :is="activeRouteComponent"
        v-if="activeRouteComponent"
        :workspace="workspace"
        @submitted="submitted"
      ></component>
    </template>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'

/**
 * The common modal to invite people into a workspace. The routes listed in the
 * left sidebar come from the `invitationRoute` registry, so other modules can
 * add their own without changing this component.
 */
export default {
  name: 'InviteModal',
  mixins: [modal],
  props: {
    workspace: {
      type: Object,
      required: true,
    },
  },
  emits: ['invite-submitted'],
  data() {
    return {
      activeRouteType: null,
    }
  },
  computed: {
    invitationRoutes() {
      return this.$registry
        .getOrderedList('invitationRoute')
        .filter((route) => route.isEnabled(this.workspace))
    },
    activeRouteComponent() {
      const route = this.invitationRoutes.find(
        (route) => route.type === this.activeRouteType
      )
      return route ? route.getComponent() : null
    },
  },
  methods: {
    show(...args) {
      this.activeRouteType = this.invitationRoutes[0]?.type ?? null
      return modal.methods.show.call(this, ...args)
    },
    submitted(invitation) {
      this.$bus.$emit('invite-submitted', invitation)
      this.$emit('invite-submitted', invitation)
      this.hide()
    },
  },
}
</script>
