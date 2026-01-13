<template>
  <div class="sidebar" :class="{ 'sidebar--collapsed': collapsed }">
    <div
      v-show="!collapsed"
      class="sidebar__section sidebar__section--scrollable"
    >
      <div class="sidebar__section-scrollable">
        <div class="sidebar__section-scrollable-inner">
          <ul class="tree">
            <component
              :is="getApplicationComponent(application)"
              v-for="application in sortedApplications"
              :key="application.id"
              :application="application"
              :page="page"
              @selected="selectedApplication"
              @selected-page="$emit('selected-page', $event)"
            ></component>
          </ul>
        </div>
      </div>
    </div>
    <div class="sidebar__section sidebar__section--bottom">
      <div class="sidebar__foot">
        <div class="sidebar__logo">
          <Logo height="14" alt="Baserow logo" />
        </div>
        <a class="sidebar__collapse-link" @click="$emit('collapse-toggled')">
          <i
            :class="{
              'iconoir-fast-arrow-right': collapsed,
              'iconoir-fast-arrow-left': !collapsed,
            }"
          ></i>
        </a>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'TemplateSidebar',
  props: {
    template: {
      type: Object,
      required: true,
    },
    applications: {
      type: Array,
      required: true,
    },
    page: {
      required: true,
      validator: (prop) => typeof prop === 'object' || prop === null,
    },
    collapsed: {
      type: Boolean,
      required: true,
    },
  },
  emits: ['collapse-toggled', 'selected-page'],
  computed: {
    sortedApplications() {
      return this.applications
        .map((a) => a)
        .sort((a, b) => {
          return a.order - b.order
        })
    },
  },
  methods: {
    getApplicationComponent(application) {
      return this.$registry
        .get('application', application.type)
        .getTemplateSidebarComponent()
    },
    selectedApplication(application) {
      this.applications.forEach((app) => {
        app._.selected = application.id === app.id
      })
    },
  },
}
</script>
