<template>
  <tr>
    <td>
      <div class="workspace-integrations-table__identity">
        <WorkspaceIntegrationAvatar :subject="integration" aria-hidden="true" />
        <span
          class="workspace-integrations-table__name"
          :title="integration.name"
          >{{ integration.name }}</span
        >
      </div>
    </td>
    <td>{{ typeName }}</td>
    <td><WorkspaceIntegrationDetailsField :row="integration" /></td>
    <!-- The actions cell, left to the table since what it offers depends on it. -->
    <slot />
  </tr>
</template>

<script setup>
import { computed } from 'vue'
import { useNuxtApp } from '#app'
import WorkspaceIntegrationAvatar from './WorkspaceIntegrationAvatar'
import WorkspaceIntegrationDetailsField from './WorkspaceIntegrationDetailsField'

/**
 * A row of an integrations table, with the Name, Type and Details cells, shared
 * by the workspace integrations table and the application integration settings.
 * Attributes such as a class or a `contextmenu` listener land on the row.
 */
const props = defineProps({
  integration: { type: Object, required: true },
})

const nuxtApp = useNuxtApp()

const typeName = computed(
  () => nuxtApp.$registry.get('integration', props.integration.type).name
)
</script>
