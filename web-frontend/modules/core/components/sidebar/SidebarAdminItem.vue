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
        :event="deactivated ? '' : 'click'"
        :to="{ name: adminType.routeName }"
        class="tree__link"
      >
        <i class="tree__icon" :class="adminType.iconClass"></i>
        <span class="tree__link-text">
          <span class="sidebar__item-name">{{ adminType.getName() }}</span>
        </span>
      </nuxt-link>
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
export default {
  name: 'SidebarAdminItem',
  props: {
    adminType: {
      required: true,
      type: Object,
    },
  },
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
  },
}
</script>
