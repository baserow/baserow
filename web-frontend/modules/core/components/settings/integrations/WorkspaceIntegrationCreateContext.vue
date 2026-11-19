<template>
  <Context ref="context" overflow-scroll max-height-if-outside-viewport>
    <ul class="context__menu">
      <li
        v-for="integrationType in integrationTypes"
        :key="integrationType.type"
        class="context__menu-item"
      >
        <a
          class="context__menu-item-link"
          @click.prevent="select(integrationType)"
        >
          <img
            v-if="integrationType.image"
            class="context__menu-item-icon"
            :src="integrationType.image"
            alt=""
          />
          <i
            v-else
            class="context__menu-item-icon"
            :class="integrationType.iconClass"
          ></i>
          {{ integrationType.name }}
        </a>
      </li>
    </ul>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'

/**
 * Lists the integration types a workspace integration can have, to pick the one
 * to create. The only type the workspace refuses, the MCP server, is managed by
 * the agents and isn't registered as an integration type in the frontend.
 */
export default {
  name: 'WorkspaceIntegrationCreateContext',
  mixins: [context],
  emits: ['select'],
  computed: {
    integrationTypes() {
      return this.$registry.getOrderedList('integration')
    },
  },
  methods: {
    select(integrationType) {
      this.hide()
      this.$emit('select', integrationType)
    },
  },
}
</script>
