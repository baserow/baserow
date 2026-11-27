<template>
  <EditorPrompt
    :action="database ? 'create_table' : 'create_database'"
    :workspace-id="workspace.id"
    :label="database?.name || workspace.name"
    :parameters="
      database
        ? { database_id: database.id, name }
        : { workspace_id: workspace.id, name }
    "
    @completed="openTable"
  />
</template>

<script setup>
import { useStore } from 'vuex'
import EditorPrompt from '@baserow/modules/core/components/EditorPrompt'
import ApplicationService from '@baserow/modules/core/services/application'
import { notifyIf } from '@baserow/modules/core/utils/error'

defineProps({
  workspace: { type: Object, required: true },
  database: { type: Object, default: null },
  name: { type: String, default: '' },
})
const emit = defineEmits(['created'])
const { $client } = useNuxtApp()
const store = useStore()
const router = useRouter()

async function openTable({ database_id: databaseId, table_id: tableId }) {
  emit('created')
  try {
    const { data } = await ApplicationService($client).get(databaseId)
    await store.dispatch('application/forceCreate', data)
    await router.push({
      name: 'database-table',
      params: { databaseId, tableId },
    })
  } catch (error) {
    notifyIf(error, 'application')
  }
}
</script>
