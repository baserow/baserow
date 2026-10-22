<template>
  <div class="template-install">
    <!-- Without a workspace there is nothing to pick. The user creates one here,
    or else is told how to get one. -->
    <p v-if="hasNoWorkspace" class="template-install__no-workspace">
      {{
        $hasPermission('create_workspace')
          ? $t('templateInstall.noWorkspace')
          : $t('templateInstall.noWorkspaceAskInvite')
      }}
    </p>
    <Dropdown
      v-else-if="isAuthenticated"
      :model-value="selectedWorkspaceId"
      class="template-install__workspace"
      :placeholder="$t('templateInstall.selectWorkspace')"
      :fixed-items="true"
      @update:model-value="chooseWorkspace"
    >
      <DropdownItem
        v-for="workspaceItem in workspaces"
        :key="workspaceItem.id"
        :name="workspaceItem.name"
        :value="workspaceItem.id"
        :disabled="!canInstallInto(workspaceItem)"
        :description="
          canInstallInto(workspaceItem)
            ? null
            : $t('templateInstall.workspaceNoPermission')
        "
      ></DropdownItem>
    </Dropdown>
    <div class="template-install__actions">
      <Button
        v-if="hasNoWorkspace && $hasPermission('create_workspace')"
        class="template-install__create-workspace"
        full-width
        @click="createWorkspaceModal.show()"
        >{{ $t('templateInstall.createWorkspace') }}</Button
      >
      <Button
        v-else
        class="template-install__use"
        full-width
        :loading="installing"
        :disabled="
          installing ||
          (isAuthenticated &&
            (selectedWorkspace === null || !canInstallInto(selectedWorkspace)))
        "
        @click="use"
        >{{ $t('templateInstall.use') }}</Button
      >
      <ButtonIcon
        ref="moreButton"
        type="secondary"
        icon="iconoir-more-vert"
        :title="$t('templateInstall.more')"
        @click="contextRef.toggle(moreButton.$el, 'top', 'right', 4)"
      ></ButtonIcon>
    </div>
    <Context ref="contextRef">
      <ul class="context__menu">
        <slot name="menu-items" :hide="hideContext"></slot>
        <li v-if="showCopyLink" class="context__menu-item">
          <a class="context__menu-item-link" @click.prevent="copyLink">
            <i class="context__menu-item-icon iconoir-link"></i>
            {{ $t('templateInstall.copyLink') }}
            <Copied ref="copiedRef"></Copied>
          </a>
        </li>
      </ul>
    </Context>
    <CreateWorkspaceModal
      v-if="isAuthenticated"
      ref="createWorkspaceModal"
      :navigate="false"
      @created="workspaceCreated"
    ></CreateWorkspaceModal>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useStore } from 'vuex'
import { useNuxtApp, useRouter, useRuntimeConfig } from '#app'

import { notifyIf } from '@baserow/modules/core/utils/error'
import { fetchPermissionsOfWorkspaces } from '@baserow/modules/core/utils/workspace'
import { injectWorkspaceSidebarVisible } from '@baserow/modules/core/composables/useWorkspaceSidebar'
import TemplateService from '@baserow/modules/core/services/template'
import CreateWorkspaceModal from '@baserow/modules/core/components/workspace/CreateWorkspaceModal'

const props = defineProps({
  template: {
    type: Object,
    required: true,
  },
  // The workspace the template is installed into by default. When null, the
  // selected or else the first workspace is used.
  workspace: {
    type: Object,
    required: false,
    default: null,
  },
  showCopyLink: {
    type: Boolean,
    required: false,
    default: true,
  },
  // Whether the latest revision of a user template is installed, which only its
  // owner may. Otherwise it's the public revision, or the owner's latest one
  // while it isn't public.
  latest: {
    type: Boolean,
    required: false,
    default: false,
  },
})

const emit = defineEmits(['installed'])

const store = useStore()
const router = useRouter()
const config = useRuntimeConfig()
const { $client, $hasPermission } = useNuxtApp()
const workspaceSidebarVisible = injectWorkspaceSidebarVisible()

const moreButton = ref(null)
const contextRef = ref(null)
const copiedRef = ref(null)
const createWorkspaceModal = ref(null)
const installing = ref(false)

const isAuthenticated = computed(() => store.getters['auth/isAuthenticated'])

// The workspaces the user can't add applications to are listed, but disabled.
const workspaces = computed(() => store.getters['workspace/getAllSorted'])

const hasNoWorkspace = computed(
  () => isAuthenticated.value && workspaces.value.length === 0
)

// Whether the user picked the workspace, which must then stay selected.
const workspaceChosen = ref(false)

/**
 * Whether the template can be installed into the workspace. Until the
 * permissions of the workspace are fetched, the global ones are used, and the
 * backend checks again.
 */
function canInstallInto(workspace) {
  return $hasPermission('workspace.create_application', workspace, workspace.id)
}

/**
 * The provided, else the selected workspace if the template can be installed
 * into it, otherwise the first one it can be installed into.
 */
function getDefaultWorkspaceId() {
  // Without a selected workspace, `getSelected` is an empty object.
  const preferred = [
    props.workspace,
    store.getters['workspace/getSelected'],
  ].filter((workspace) => workspace?.id !== undefined)
  const candidates = [...preferred, ...workspaces.value]
  const workspace = candidates.find(canInstallInto) || candidates[0]
  return workspace?.id ?? null
}

const selectedWorkspaceId = ref(getDefaultWorkspaceId())

const selectedWorkspace = computed(
  () =>
    workspaces.value.find(({ id }) => id === selectedWorkspaceId.value) || null
)

function chooseWorkspace(workspaceId) {
  workspaceChosen.value = true
  selectedWorkspaceId.value = workspaceId
}

/**
 * The permissions of a workspace are only fetched when needed, so the ones of the
 * listed workspaces are fetched here. A workspace the template can't be installed
 * into is then replaced with one it can, unless the user picked it.
 */
async function loadPermissions() {
  if (!isAuthenticated.value) {
    return
  }
  await fetchPermissionsOfWorkspaces(store, workspaces.value)
  if (
    !workspaceChosen.value &&
    (selectedWorkspace.value === null ||
      !canInstallInto(selectedWorkspace.value))
  ) {
    selectedWorkspaceId.value = getDefaultWorkspaceId()
  }
}

onMounted(loadPermissions)

async function use() {
  if (!isAuthenticated.value) {
    // Sends the user back to this template's page after logging in.
    const original = templateRoute().fullPath
    await router.push({ name: 'login', query: { original } })
    return
  }

  installing.value = true
  const workspaceId = selectedWorkspaceId.value

  try {
    const { data } = await TemplateService($client).asyncInstall(
      workspaceId,
      props.template.id,
      { latest: props.latest }
    )
    // The user stays where they are. The progress shows in the sidebar if it
    // lists the workspace that receives the template, so not when it's collapsed
    // or on a page without a workspace, otherwise in a toast. Added before the
    // job, whose end updates the toast.
    const sidebarShowsProgress =
      workspaceSidebarVisible.value &&
      workspaceId === store.getters['workspace/getSelected']?.id
    if (!sidebarShowsProgress) {
      await store.dispatch('toast/add', {
        type: 'installTemplate',
        data: { jobId: data.id, template_name: props.template.name },
      })
    }
    await store.dispatch('job/create', data)
    emit('installed')
  } catch (error) {
    notifyIf(error, 'template')
  } finally {
    installing.value = false
  }
}

// The user stays on the template, which is then installed into the new workspace.
function workspaceCreated(workspace) {
  chooseWorkspace(workspace.id)
}

function hideContext() {
  contextRef.value.hide()
}

function templateRoute() {
  return router.resolve({
    name: 'template',
    params: { slug: props.template.slug },
  })
}

async function copyLink() {
  const { href } = templateRoute()
  await navigator.clipboard.writeText(
    new URL(href, config.public.publicWebFrontendUrl).toString()
  )
  copiedRef.value.show()
}
</script>
