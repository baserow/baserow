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
      <div
        v-if="title || previousPage"
        ref="header"
        class="invite-modal__header"
        tabindex="-1"
      >
        <Button
          v-if="previousPage"
          class="invite-modal__back"
          type="secondary"
          size="small"
          icon="iconoir-arrow-left"
          @click="goBack"
        >
          {{
            $t('inviteModal.backTo', {
              level: previousLevel,
              title: previousTitle,
            })
          }}
        </Button>
        <h2 v-if="title" class="invite-modal__title">{{ title }}</h2>
        <div v-if="subtitle" class="invite-modal__subtitle">{{ subtitle }}</div>
      </div>
      <component
        :is="activeRouteComponent"
        v-if="activeRouteComponent"
        :key="`${pageRevision}:${activeRouteType}`"
        :workspace="workspace"
        :target="currentTarget"
        :target-type="targetType"
        @navigate="navigate"
        @submitted="submitted"
        @close="close"
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
 * invitations to close the modal once they were sent, or `close` when it leads
 * somewhere else. A route can emit `navigate` with another registered target
 * to replace the content in this modal. Back restores the previous target and
 * tab, remounting its route to refresh access data after changes at another level.
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
  emits: ['invite-submitted', 'close'],
  data() {
    return {
      activeRouteType: null,
      navigatedTarget: null,
      history: [],
      pageRevision: 0,
    }
  },
  computed: {
    currentTarget() {
      return this.navigatedTarget || this.target
    },
    previousPage() {
      return this.history[this.history.length - 1] || null
    },
    previousLevel() {
      if (!this.previousPage) {
        return ''
      }
      const { target } = this.previousPage
      return this.$registry
        .get('invitationTarget', target.type)
        .getNavigationLabel(this.workspace, target)
    },
    previousTitle() {
      if (!this.previousPage) {
        return ''
      }
      const { target } = this.previousPage
      return (
        this.$registry
          .get('invitationTarget', target.type)
          .getTitle(this.workspace, target) || this.workspace.name
      )
    },
    targetType() {
      return this.$registry.get('invitationTarget', this.currentTarget.type)
    },
    title() {
      return this.targetType.getTitle(this.workspace, this.currentTarget)
    },
    subtitle() {
      return this.targetType.getSubtitle(this.workspace, this.currentTarget)
    },
    invitationRoutes() {
      return this.$registry
        .getOrderedList('invitationRoute')
        .filter((route) => route.isEnabled(this.workspace, this.currentTarget))
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
      this.history = []
      this.navigatedTarget = null
      this.pageRevision++
      this.activeRouteType = this.invitationRoutes[0]?.type ?? null
      return modal.methods.show.call(this, ...args)
    },
    /** Replace the target while keeping its previous target and selected tab. */
    navigate(target) {
      this.history.push({
        target: this.currentTarget,
        routeType: this.activeRouteType,
      })
      this.navigatedTarget = target
      this.activeRouteType = this.invitationRoutes[0]?.type ?? null
      this.pageRevision++
      this.$nextTick(() => this.$refs.header?.focus())
    },
    /** Return to the previous target with fresh route data. */
    goBack() {
      const previous = this.history.pop()
      if (!previous) {
        return
      }
      this.navigatedTarget = previous.target
      this.activeRouteType = this.invitationRoutes.some(
        (route) => route.type === previous.routeType
      )
        ? previous.routeType
        : (this.invitationRoutes[0]?.type ?? null)
      this.pageRevision++
      this.$nextTick(() => this.$refs.header?.focus())
    },
    submitted(invitations) {
      this.$emit('invite-submitted', invitations)
      this.hide()
    },
    close() {
      this.hide()
      this.$emit('close')
    },
  },
}
</script>
