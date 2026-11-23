<template>
  <ul v-sidebar-tab-order class="context__menu">
    <WorkspaceActionItem :action="inviteAction" />
    <li
      v-if="canInvite"
      class="sidebar-workspace-menu__separator"
      role="separator"
    ></li>
    <WorkspaceActionItem v-if="canListMembers" :action="actions.members" />
    <WorkspaceActionItem :action="actions.aiProviders" />
    <component
      :is="component"
      v-for="(component, index) in extensions"
      :key="index"
      :workspace="workspace"
      @hide="$emit('hide')"
    />
    <WorkspaceActionItem :action="{ ...actions.trash, icon: 'iconoir-bin' }" />
    <li class="sidebar-workspace-menu__separator" role="separator"></li>
    <WorkspaceActionItem :action="actions.exportData" />
    <WorkspaceActionItem :action="actions.importData" />
    <WorkspaceActionItem :action="renameAction" />
    <WorkspaceActionItem :action="leaveAction" />
    <WorkspaceActionItem :action="actions.delete" separator />
  </ul>
  <InviteModal v-if="canInvite" ref="inviteModal" :workspace="workspace" />
  <Modal v-if="renameAction" ref="renameModal">
    <h2 class="box__title">{{ $t('workspaceContext.renameWorkspace') }}</h2>
    <WorkspaceForm :default-name="workspace.name" @submitted="renameWorkspace">
      <div class="actions">
        <div class="align-right">
          <Button type="primary" :loading="renaming" :disabled="renaming">
            {{ $t('action.save') }}
          </Button>
        </div>
      </div>
    </WorkspaceForm>
  </Modal>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useNuxtApp } from '#imports'
import vSidebarTabOrder from '@baserow/modules/core/directives/sidebarTabOrder'
import { notifyIf } from '@baserow/modules/core/utils/error'
import InviteModal from '@baserow/modules/core/components/invitation/InviteModal'
import WorkspaceActionItem from '@baserow/modules/core/components/workspace/WorkspaceActionItem.vue'
import WorkspaceForm from '@baserow/modules/core/components/workspace/WorkspaceForm'

const props = defineProps({
  workspace: {
    type: Object,
    required: true,
  },
  actions: {
    type: Object,
    required: true,
  },
  extensions: {
    type: Array,
    required: true,
  },
})
const emit = defineEmits(['hide'])
const { $hasPermission, $store } = useNuxtApp()

const inviteModal = ref(null)
const renameModal = ref(null)
const renaming = ref(false)
const canInvite = computed(() =>
  $hasPermission(
    'workspace.create_invitation',
    props.workspace,
    props.workspace.id
  )
)
const canListMembers = computed(() =>
  $hasPermission(
    'workspace.list_workspace_users',
    props.workspace,
    props.workspace.id
  )
)
const inviteAction = computed(() =>
  canInvite.value
    ? {
        icon: 'iconoir-add-user',
        label: 'sidebar.inviteOthers',
        run: () => {
          emit('hide')
          inviteModal.value.show()
        },
      }
    : null
)
const renameAction = computed(() =>
  props.actions.rename
    ? {
        ...props.actions.rename,
        run: () => {
          emit('hide')
          renameModal.value.show()
        },
      }
    : null
)
const leaveAction = computed(() => ({
  ...props.actions.leave,
  run: () => {
    emit('hide')
    props.actions.leave.run()
  },
}))

async function renameWorkspace(values) {
  if (renaming.value) {
    return
  }
  renaming.value = true
  try {
    await $store.dispatch('workspace/update', {
      workspace: props.workspace,
      values,
    })
    renameModal.value?.hide()
  } catch (error) {
    notifyIf(error, 'workspace')
  } finally {
    renaming.value = false
  }
}
</script>
