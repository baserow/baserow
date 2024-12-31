<template>
  <li
    class="tree__item"
    :class="{
      'tree__item--loading': application._.loading,
    }"
  >
    <div
      class="tree__action"
      :class="{ 'tree__action--highlighted': application._.selected }"
    >
      <a class="tree__link" @click="selectDashboard(application)">
        <i class="tree__icon" :class="application._.type.iconClass"></i>
        <span class="tree__link-text">{{ application.name }}</span>
      </a>
    </div>
  </li>
</template>

<script>
import { DashboardApplicationType } from '@baserow/modules/dashboard/applicationTypes'

export default {
  name: 'DashboardTemplateSidebar',
  props: {
    application: {
      type: Object,
      required: true,
    },
    page: {
      required: true,
      validator: (prop) => typeof prop === 'object' || prop === null,
    },
  },
  methods: {
    selectDashboard(application) {
      this.$emit('selected', application)
      this.$emit('selected-page', {
        application: DashboardApplicationType.getType(),
        value: {
          dashboard: application,
        },
      })
    },
  },
}
</script>
