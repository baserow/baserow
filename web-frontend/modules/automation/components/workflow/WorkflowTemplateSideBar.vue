<template>
  <li
    class="tree__item"
    :class="{
      'tree__item--loading': application._.loading,
    }"
  >
    <div class="tree__action">
      <a class="tree__link" @click="$emit('selected', application)">
        <i class="tree__icon" :class="application._.type.iconClass"></i>
        <span class="tree__link-text">{{ application.name }}</span>
      </a>
    </div>
    <template v-if="application._.selected">
      <ul class="tree__subs">
        <li
          v-for="workflow in orderedWorkflows"
          :key="workflow.id"
          class="tree__sub"
          :class="{ active: isPageActive(workflow) }"
        >
          <a class="tree__sub-link" @click="selectPage(application, workflow)">
            {{ workflow.name }}
          </a>
        </li>
      </ul>
    </template>
  </li>
</template>

<script>
import { AutomationApplicationType } from '@baserow/modules/automation/applicationTypes'

export default {
  name: 'TemplateSidebar',
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
  emits: ['selected', 'selected-page'],
  computed: {
    orderedWorkflows() {
      return this.$store.getters['automationWorkflow/getWorkflows'](
        this.application
      )
    },
  },
  methods: {
    selectPage(application, workflow) {
      this.$emit('selected-page', {
        application: AutomationApplicationType.getType(),
        value: {
          automation: application,
          workflow,
        },
      })
    },
    isPageActive(page) {
      return (
        this.page !== null &&
        this.page.application === AutomationApplicationType.getType() &&
        this.page.value.workflow.id === page.id
      )
    },
  },
}
</script>
