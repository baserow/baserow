<template>
  <CrudTable
    v-bind="tableLayout"
    ref="table"
    class="management-table management-table--invitation-links"
    :service="service"
    :columns="columns"
    row-id-key="id"
    :search-placeholder="$t('invitationLinksSettings.search')"
    @update-link-role="updateRole"
    @delete-link="showDeleteModal"
  >
    <template #title="{ count }">
      {{
        $t('invitationLinksSettings.title', {
          count,
          workspace: workspace.name,
        })
      }}
    </template>
    <template #subtitle>
      {{ $t('invitationLinksSettings.description') }}
    </template>
    <template #empty>
      <div class="placeholder">
        <div class="placeholder__icon">
          <i class="iconoir-link" aria-hidden="true"></i>
        </div>
        <h2 class="placeholder__header">
          {{ $t('invitationLinksSettings.emptyTitle') }}
        </h2>
        <p class="placeholder__content">
          {{ $t('invitationLinksSettings.emptyDescription') }}
        </p>
      </div>
    </template>
  </CrudTable>
  <ConfirmModal
    ref="adminConfirmModal"
    :title="$t('invitationLinkAdminConfirmModal.title')"
    :message="adminWarning"
    :confirm-label="$t('invitationLinkAdminConfirmModal.confirm')"
    danger
    @hidden="pendingRoleChange = null"
    @confirm="confirmRoleChange"
  />
  <InvitationLinkDeleteModal
    v-if="deletingRow"
    ref="deleteModal"
    :workspace="workspace"
    :target="deletingRow.target"
    :target-type="deletingRow.targetType"
    @deleted="deleted"
  />
</template>

<script setup>
import { computed, nextTick, ref } from 'vue'
import { useNuxtApp } from '#imports'
import { getManagementTableLayout } from '@baserow/modules/core/utils/managementTable'
import { notifyIf } from '@baserow/modules/core/utils/error'
import CrudTable from '@baserow/modules/core/components/crudTable/CrudTable'
import CrudTableColumn from '@baserow/modules/core/crudTable/crudTableColumn'
import BooleanIconField from '@baserow/modules/core/components/crudTable/fields/BooleanIconField'
import ManagementNameField from '@baserow/modules/core/components/settings/ManagementNameField'
import ConfirmModal from '@baserow/modules/core/components/modals/ConfirmModal'
import InvitationLinkDeleteModal from '@baserow/modules/core/components/invitation/InvitationLinkDeleteModal'
import WorkspaceService from '@baserow/modules/core/services/workspace'
import InvitationLinkTargetField from './InvitationLinkTargetField'
import InvitationLinkRoleField from './InvitationLinkRoleField'
import InvitationLinkActionsField from './InvitationLinkActionsField'

/**
 * Lists every invitation link of the workspace that the user can manage, to
 * the workspace itself or to one of its objects, like a table or a team. The
 * role of a link can be changed and a link can be copied or deleted, through
 * the invitation target type of the link like where it was created. Links are
 * only created where they lead to, so there is no create button.
 */
const props = defineProps({
  workspace: { type: Object, required: true },
})

const { $i18n, $registry, $client } = useNuxtApp()

const table = ref(null)
const adminConfirmModal = ref(null)
const deleteModal = ref(null)
const pendingRoleChange = ref(null)
const deletingRow = ref(null)

/**
 * Pairs a link with its invitation target, which knows how to show and change
 * it. Links of a target type that isn't available are left out.
 */
function toRow(invitationLink) {
  for (const targetType of Object.values(
    $registry.getAll('invitationTarget')
  )) {
    const target = targetType.getTargetFromInvitationLink(
      props.workspace,
      invitationLink
    )
    if (target) {
      return {
        ...invitationLink,
        label:
          invitationLink.name || $i18n.t('invitationLinksSettings.unnamed'),
        target,
        targetType,
        targetName: targetType.getInvitationLinkTargetName(
          props.workspace,
          target
        ),
      }
    }
  }
  return null
}

/**
 * Sorts like the services of the other management tables do: CrudTable's
 * `desc`, which the first click on a column applies, puts the rows in A to Z
 * order.
 */
function compareRows(sorts) {
  return (a, b) => {
    for (const { key, direction } of sorts) {
      const order = String(a[key]).localeCompare(String(b[key]))
      if (order !== 0) {
        return direction === 'desc' ? order : -order
      }
    }
    return a.id - b.id
  }
}

/**
 * The links come in one response, so they are searched and sorted here.
 */
const service = computed(() => ({
  options: { isPaginated: false, baseUrl: null, urlParams: {} },
  async fetch(baseUrl, page, searchQuery, sorts) {
    const { data } = await WorkspaceService(
      $client
    ).fetchManageableInvitationLinks(props.workspace.id)
    const search = (searchQuery || '').trim().toLowerCase()
    const rows = data
      .map(toRow)
      .filter(Boolean)
      .filter(
        (row) =>
          !search ||
          row.label.toLowerCase().includes(search) ||
          row.targetName.toLowerCase().includes(search)
      )
      .sort(compareRows(sorts))
    return { data: rows }
  },
}))

const columns = computed(() => [
  new CrudTableColumn(
    'label',
    () => $i18n.t('invitationLinksSettings.name'),
    ManagementNameField,
    true,
    true,
    false,
    { icon: 'iconoir-link', color: 'neutral' }
  ),
  new CrudTableColumn(
    'targetName',
    () => $i18n.t('invitationLinksSettings.to'),
    InvitationLinkTargetField,
    true
  ),
  new CrudTableColumn(
    'permissions',
    () => $i18n.t('invitationLinksSettings.inviteAs'),
    InvitationLinkRoleField,
    false,
    false,
    false,
    { workspace: props.workspace }
  ),
  new CrudTableColumn(
    'has_password',
    () => $i18n.t('invitationLinksSettings.passwordProtected'),
    BooleanIconField,
    false,
    false,
    false,
    {
      icon: 'iconoir-lock',
      title: $i18n.t('inviteModal.linkPasswordProtected'),
    }
  ),
  new CrudTableColumn(
    null,
    null,
    InvitationLinkActionsField,
    false,
    false,
    true
  ),
])

const tableLayout = computed(() => {
  const layout = getManagementTableLayout(columns.value, 'permissions')
  layout.columnWidths.label = 'clamp(160px, 30cqw, 260px)'
  layout.columnWidths.targetName = 'auto'
  layout.columnWidths.permissions = '170px'
  layout.columnWidths.has_password = '88px'
  layout.columnWidths.null = '76px'
  // The modal is narrower than a settings page.
  layout.minTableWidth = '600px'
  return layout
})

const adminWarning = computed(() => {
  const row = pendingRoleChange.value?.row
  return row
    ? row.targetType.getInvitationLinkAdminWarning(props.workspace, row.target)
    : ''
})

async function changeRole(row, uid) {
  try {
    const updated = await row.targetType.updateInvitationLink(
      props.workspace,
      row.target,
      row,
      { permissions: uid }
    )
    table.value.updateRow({ id: row.id, permissions: updated.permissions })
  } catch (error) {
    notifyIf(error, 'workspace')
  }
}

/**
 * Changes the role right away, unless the link would grant the admin role, in
 * which case it waits for the confirmation like where the link was created.
 */
async function updateRole({ row, uid }) {
  if (uid === row.permissions) {
    return
  }
  if (
    row.targetType.invitationLinkGrantsAdmin(props.workspace, row.target, uid)
  ) {
    pendingRoleChange.value = { row, uid }
    await nextTick()
    adminConfirmModal.value.show()
  } else {
    await changeRole(row, uid)
  }
}

function confirmRoleChange() {
  const change = pendingRoleChange.value
  pendingRoleChange.value = null
  adminConfirmModal.value.hide()
  if (change) {
    changeRole(change.row, change.uid)
  }
}

async function showDeleteModal(row) {
  deletingRow.value = row
  await nextTick()
  deleteModal.value.show(row)
}

function deleted(invitationLink) {
  table.value.deleteRow(invitationLink.id)
}
</script>
