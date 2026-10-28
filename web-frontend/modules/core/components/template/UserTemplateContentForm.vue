<template>
  <div>
    <FormGroup
      :label="$t('userTemplateContentForm.workspace')"
      small-label
      required
      class="margin-bottom-2"
    >
      <Dropdown
        :model-value="modelValue.workspaceId"
        :disabled="disabled"
        @update:model-value="chooseWorkspace"
      >
        <DropdownItem
          v-for="workspace in workspaces"
          :key="workspace.id"
          :name="workspace.name"
          :value="workspace.id"
          :disabled="getDisabledReason(workspace) !== null"
          :description="getDisabledReason(workspace)"
        />
      </Dropdown>
    </FormGroup>

    <ApplicationSelector
      v-if="selectedWorkspace"
      :key="selectedWorkspace.id"
      :workspace="selectedWorkspace"
      :selected-application-ids="modelValue.applicationIds"
      :disabled="disabled"
      :title="$t('userTemplateContentForm.applications')"
      class="margin-bottom-2"
      @update="update({ applicationIds: $event })"
    />

    <Alert type="info-neutral" class="margin-bottom-0">
      <template #title>
        {{ $t('userTemplateContentForm.noticeTitle') }}
      </template>
      <ul class="user-template-form__notice-list">
        <li>{{ $t('userTemplateContentForm.noticeSecrets') }}</li>
        <li>{{ $t('userTemplateContentForm.noticePasswords') }}</li>
        <li>{{ $t('userTemplateContentForm.noticePeople') }}</li>
        <li>{{ $t('userTemplateContentForm.noticePersonalViews') }}</li>
        <li>{{ $t('userTemplateContentForm.noticeReferences') }}</li>
      </ul>
      <p>{{ $t('userTemplateContentForm.noticeRest') }}</p>
    </Alert>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useNuxtApp } from '#app'

import { fetchPermissionsOfWorkspaces } from '@baserow/modules/core/utils/workspace'

import ApplicationSelector from '@baserow/modules/core/components/export/ApplicationSelector'

const props = defineProps({
  // The content: `{ workspaceId, applicationIds }`. Without a workspace, one is
  // selected when the form is shown.
  modelValue: {
    type: Object,
    required: true,
  },
  // The workspace and applications to select first, like the ones the content
  // was copied from before: `{ workspaceId, applicationIds }`. Only used while
  // the user can still export that workspace.
  preselect: {
    type: Object,
    required: false,
    default: null,
  },
  disabled: {
    type: Boolean,
    required: false,
    default: false,
  },
})

// `update:valid` tells whether the content can be submitted.
const emit = defineEmits(['update:modelValue', 'update:valid'])

const { $store, $hasPermission, $i18n } = useNuxtApp()

// Whether the user picked the workspace, which must then stay selected.
const workspaceChosen = ref(false)

const workspaces = computed(() => $store.getters['workspace/getAllSorted'])

const selectedWorkspace = computed(
  () =>
    workspaces.value.find(
      (workspace) => workspace.id === props.modelValue.workspaceId
    ) || null
)

/**
 * Explains why the content can't be copied from the workspace, or is null when
 * it can.
 */
function getDisabledReason(workspace) {
  if (workspace === null) {
    return ''
  }
  if ($store.getters['application/getAllOfWorkspace'](workspace).length === 0) {
    return $i18n.t('userTemplateContentForm.workspaceEmpty')
  }
  if (!$hasPermission('workspace.export', workspace, workspace.id)) {
    return $i18n.t('userTemplateContentForm.workspaceNoPermission')
  }
  return null
}

/**
 * The selected workspace if the content can be copied from it, otherwise the
 * first one it can be copied from.
 */
function getDefaultWorkspaceId() {
  const selected = $store.getters['workspace/getSelected']
  const candidates = selected
    ? [selected, ...workspaces.value]
    : [...workspaces.value]
  const workspace =
    candidates.find((w) => getDisabledReason(w) === null) || candidates[0]
  return workspace?.id ?? null
}

const valid = computed(
  () =>
    getDisabledReason(selectedWorkspace.value) === null &&
    props.modelValue.applicationIds.length > 0
)

watch(valid, (value) => emit('update:valid', value), { immediate: true })

function update(values) {
  emit('update:modelValue', { ...props.modelValue, ...values })
}

function getApplicationIds(workspaceId) {
  const workspace = workspaces.value.find(({ id }) => id === workspaceId)
  return workspace
    ? $store.getters['application/getAllOfWorkspace'](workspace).map(
        (application) => application.id
      )
    : []
}

/**
 * A different workspace has different applications, so the selection starts
 * again with all of them.
 */
function selectWorkspace(workspaceId) {
  update({ workspaceId, applicationIds: getApplicationIds(workspaceId) })
}

function chooseWorkspace(workspaceId) {
  workspaceChosen.value = true
  selectWorkspace(workspaceId)
}

/**
 * Starts with the preselected workspace while the user still has it, keeping only
 * the preselected applications it still has. Otherwise with the default one.
 */
function selectFirstWorkspace() {
  const preselected =
    props.preselect &&
    workspaces.value.find(({ id }) => id === props.preselect.workspaceId)
  if (preselected) {
    const applicationIds = getApplicationIds(preselected.id)
    update({
      workspaceId: preselected.id,
      applicationIds: applicationIds.filter((id) =>
        props.preselect.applicationIds.includes(id)
      ),
    })
    return
  }
  selectWorkspace(getDefaultWorkspaceId())
}

/**
 * The permissions of a workspace are only fetched when needed, so the ones of
 * the workspaces the content can be copied from are fetched here. Until then the
 * global permissions are used and the backend checks again. A workspace that
 * can't be exported is then replaced with one that can.
 */
async function loadPermissions() {
  await fetchPermissionsOfWorkspaces($store, workspaces.value)
  if (
    props.disabled ||
    workspaceChosen.value ||
    getDisabledReason(selectedWorkspace.value) === null
  ) {
    return
  }
  selectWorkspace(getDefaultWorkspaceId())
}

onMounted(() => {
  // A running job keeps the content it was started with.
  if (props.modelValue.workspaceId === null && !props.disabled) {
    selectFirstWorkspace()
  }
  loadPermissions()
})

defineExpose({ loadPermissions })
</script>
