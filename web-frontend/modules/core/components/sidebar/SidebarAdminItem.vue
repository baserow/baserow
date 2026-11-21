<template>
  <li
    class="tree__item"
    :class="{
      active: $route.matched.some(({ name }) => name === adminType.routeName),
    }"
  >
    <div
      class="tree__action sidebar__action"
      :class="{
        'tree__action--deactivated': deactivated,
        'tree__action--has-counter': badgeCount > 0,
      }"
    >
      <a
        v-if="deactivated"
        href="#"
        class="tree__link"
        @click="deactivatedModal ? $refs.deactivatedModal.show() : null"
      >
        <i class="tree__icon iconoir-lock"></i>
        <span class="tree__link-text">
          <span class="sidebar__item-name">{{ adminType.getName() }}</span>
        </span>
      </a>
      <nuxt-link
        v-else
        v-slot="{ href, navigate, isExactActive, prefetch, shouldPrefetch }"
        :to="{ name: adminType.routeName }"
        custom
        prefetch-on="interaction"
      >
        <a
          :href="href"
          class="tree__link"
          :aria-current="isExactActive ? 'page' : undefined"
          @click="activate($event, navigate)"
          @pointerenter="shouldPrefetch('interaction') && prefetch()"
          @focus="shouldPrefetch('interaction') && prefetch()"
        >
          <i class="tree__icon" :class="adminType.iconClass"></i>
          <span class="tree__link-text">
            <span class="sidebar__item-name">{{ adminType.getName() }}</span>
          </span>
        </a>
      </nuxt-link>
      <BadgeCounter
        v-if="badgeCount > 0"
        class="tree__counter badge-counter--warning"
        :count="badgeCount"
        :limit="10"
      ></BadgeCounter>
    </div>
    <component
      :is="deactivatedModal[0]"
      v-if="deactivatedModal"
      ref="deactivatedModal"
      v-bind="deactivatedModal[1]"
    ></component>
  </li>
</template>

<script>
import BadgeCounter from '@baserow/modules/core/components/BadgeCounter'

export default {
  name: 'SidebarAdminItem',
  components: { BadgeCounter },
  props: {
    adminType: {
      required: true,
      type: Object,
    },
  },
  emits: ['activate'],
  computed: {
    adminTypeObject() {
      return this.$registry.get('admin', this.adminType.type)
    },
    deactivated() {
      return this.adminTypeObject.isDeactivated()
    },
    deactivatedModal() {
      return this.adminTypeObject.getDeactivatedModal()
    },
    badgeCount() {
      return this.adminTypeObject.getBadgeCount()
    },
  },
  mounted() {
    this.adminTypeObject.loadBadgeCount()
  },
  methods: {
    async activate(event, navigate) {
      if (
        event.defaultPrevented ||
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey
      ) {
        return
      }

      await navigate(event)
      // A click can leave the route unchanged when the admin page is already open.
      if (this.$router.currentRoute.value.name === this.adminType.routeName) {
        this.$emit('activate')
      }
    },
  },
}
</script>
