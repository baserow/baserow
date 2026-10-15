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
      <div v-if="title" class="invite-modal__header">
        <h2 class="invite-modal__title">{{ title }}</h2>
        <div v-if="subtitle" class="invite-modal__subtitle">{{ subtitle }}</div>
      </div>
      <component
        :is="activeRouteComponent"
        v-if="activeRouteComponent"
        :workspace="workspace"
        :target="target"
        :target-type="targetType"
        @submitted="submitted"
      ></component>
    </template>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'

/**
 * The common modal to invite people into a workspace, or into one object of it
 * when opened with a more specific target. The routes listed in the left sidebar
 * come from the `invitationRoute` registry and the behaviour of the target from
 * the `invitationTarget` registry, so other modules can add their own without
 * changing this component. A route emits `submitted` with the created
 * invitations to close the modal once they were sent.
 */
export default {
  name: 'InviteModal',
  mixins: [modal],
  props: {
    workspace: {
      type: Object,
      required: true,
    },
    /**
     * What people are invited to: `{ type: 'workspace' }` by default, or a target
     * registered by another module such as `{ type: 'scope', scopeType, scope }`.
     */
    target: {
      type: Object,
      required: false,
      default: () => ({ type: 'workspace' }),
    },
  },
  emits: ['invite-submitted'],
  data() {
    return {
      activeRouteType: null,
    }
  },
  computed: {
    targetType() {
      return this.$registry.get('invitationTarget', this.target.type)
    },
    title() {
      return this.targetType.getTitle(this.workspace, this.target)
    },
    subtitle() {
      return this.targetType.getSubtitle(this.workspace, this.target)
    },
    invitationRoutes() {
      return this.$registry
        .getOrderedList('invitationRoute')
        .filter((route) => route.isEnabled(this.workspace, this.target))
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
    submitted(invitations) {
      this.$emit('invite-submitted', invitations)
      this.hide()
    },
  },
}
</script>
