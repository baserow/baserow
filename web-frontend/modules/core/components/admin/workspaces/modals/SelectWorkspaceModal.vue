<template>
  <Context
    ref="context"
    class="select-workspace-modal"
    :style="{ '--select-workspace-body-height': `${MAX_BODY_HEIGHT}px` }"
    force-position
    role="dialog"
    :aria-label="$t('selectWorkspaceModal.title')"
    @hidden="hidden"
  >
    <button
      type="button"
      class="select-workspace-modal__close"
      :aria-label="$t('action.close')"
      @click="context.hide()"
    >
      <i class="iconoir-cancel" />
    </button>
    <CrudTable
      :key="selectedOnly ? 'selected' : 'all'"
      ref="table"
      :columns="columns"
      :service="service"
      :column-widths="{ selected: '40px', id: '72px' }"
      :search-placeholder="$t('selectWorkspaceModal.search')"
      row-id-key="id"
      fixed-layout
      @rows-update="updatePosition"
    >
      <template #header-filters>
        <SegmentControl
          class="select-workspace-modal__views"
          size="small"
          :active-index="selectedOnly ? 1 : 0"
          :segments="[
            { label: $t('selectWorkspaceModal.allWorkspaces') },
            {
              label: $t('selectWorkspaceModal.selectedWorkspaces', {
                count: selectedWorkspaces.length,
              }),
            },
          ]"
          @update:active-index="selectedOnly = $event === 1"
        />
      </template>
      <template v-if="selectedOnly" #empty>
        <p>{{ $t('selectWorkspaceModal.noSelectedWorkspaces') }}</p>
      </template>
      <template #rows="{ rows }">
        <tr
          v-for="workspace in rows"
          :key="workspace.id"
          class="data-table__table-row select-workspace-modal__row"
          @click="select(workspace)"
        >
          <td class="data-table__table-cell">
            <Checkbox
              :checked="selectedIds.includes(workspace.id)"
              @click.stop
              @input="select(workspace)"
              >{{ workspace.value }}</Checkbox
            >
          </td>
          <td class="data-table__table-cell select-workspace-modal__id">
            {{ workspace.id }}
          </td>
          <td class="data-table__table-cell">
            <button
              type="button"
              class="select-workspace-modal__option"
              @click.stop="select(workspace)"
            >
              <span
                class="select-workspace-modal__name"
                :title="workspace.value"
                >{{ workspace.value }}</span
              >
            </button>
          </td>
        </tr>
      </template>
    </CrudTable>
  </Context>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useNuxtApp } from '#app'

import CrudTable from '@baserow/modules/core/components/crudTable/CrudTable'
import CrudTableColumn from '@baserow/modules/core/crudTable/crudTableColumn'
import baseService from '@baserow/modules/core/crudTable/baseService'
import SimpleField from '@baserow/modules/core/components/crudTable/fields/SimpleField'
import { ADMIN_WORKSPACE_OPTIONS_URL } from '@baserow/modules/core/services/admin/workspaces'
import SegmentControl from '@baserow/modules/core/components/SegmentControl'

const props = defineProps({
  selectedWorkspaces: { type: Array, default: () => [] },
})
const emit = defineEmits(['selected', 'unselected', 'hidden'])
const { $client, $i18n } = useNuxtApp()
const context = ref(null)
const table = ref(null)
const selectedOnly = ref(false)
const selectedIds = computed(() => props.selectedWorkspaces.map(({ id }) => id))
// Header, ten rows, and the table's outer border.
const MAX_BODY_HEIGHT = 33 * 11 + 2
const EDGE = 12
const GAP = 6
let anchor = null
let generation = 0
const allWorkspacesService = baseService($client, ADMIN_WORKSPACE_OPTIONS_URL)
const selectedWorkspacesService = {
  options: { isPaginated: false },
  fetch(_baseUrl, _page, search) {
    const query = String(search || '')
      .trim()
      .toLowerCase()
    const results = props.selectedWorkspaces
      .filter(
        ({ id, name }) =>
          !query ||
          name.toLowerCase().includes(query) ||
          String(id).includes(query)
      )
      .map(({ id, name }) => ({ id, value: name }))
    return Promise.resolve({ data: { count: results.length, results } })
  },
}
const service = computed(() =>
  selectedOnly.value ? selectedWorkspacesService : allWorkspacesService
)
const columns = [
  new CrudTableColumn('selected', '', SimpleField),
  new CrudTableColumn(
    'id',
    () => $i18n.t('workspacesAdminTable.id'),
    SimpleField
  ),
  new CrudTableColumn(
    'value',
    () => $i18n.t('workspacesAdminTable.name'),
    SimpleField
  ),
]

function select(workspace) {
  const isSelected = selectedIds.value.includes(workspace.id)
  if (isSelected) {
    emit('unselected', workspace.id)
  } else {
    emit('selected', { id: workspace.id, name: workspace.value })
  }
  updatePosition()
}

watch(
  () => props.selectedWorkspaces,
  async () => {
    if (selectedOnly.value) await table.value?.refresh({ silent: true })
    updatePosition()
  },
  { deep: true }
)

function verticalPlacement(target, preferredHeight = Infinity) {
  const targetTop = Math.min(target.top, window.innerHeight - EDGE)
  const targetBottom = Math.max(target.bottom, EDGE)
  const below = window.innerHeight - targetBottom - GAP - EDGE
  const above = targetTop - GAP - EDGE
  const vertical = below >= preferredHeight || below >= above ? 'bottom' : 'top'
  const available = Math.max(0, vertical === 'bottom' ? below : above)
  const verticalOffset =
    GAP +
    (vertical === 'top' ? target.top - targetTop : targetBottom - target.bottom)
  return { vertical, available, verticalOffset }
}

async function updatePosition() {
  await nextTick()
  if (!anchor || !context.value?.isOpen()) return
  const panel = context.value.getTeleportedElement()
  const panelRect = panel.getBoundingClientRect()
  const body = panel.querySelector('.data-table__body')
  if (!body) return
  const preferredHeight = panelRect.height - body.offsetHeight + MAX_BODY_HEIGHT
  const target = anchor.getBoundingClientRect()
  const { vertical, available, verticalOffset } = verticalPlacement(
    target,
    preferredHeight
  )
  panel.style.setProperty(
    '--select-workspace-available-height',
    `${available}px`
  )
  const left = Math.max(
    EDGE,
    Math.min(target.left, window.innerWidth - panelRect.width - EDGE)
  )
  await context.value.show(
    anchor,
    vertical,
    'left',
    verticalOffset,
    left - target.left
  )
}

function onScroll(event) {
  const panel = context.value?.getTeleportedElement()
  if (!panel?.contains(event.target)) updatePosition()
}

function onKeyup(event) {
  if (event.key === 'Escape') context.value?.hide()
}

function cleanup() {
  window.removeEventListener('scroll', onScroll, true)
  window.removeEventListener('resize', updatePosition)
  window.removeEventListener('keyup', onKeyup)
}

function hidden() {
  generation++
  cleanup()
  emit('hidden')
}

async function show(target, showSelected = false) {
  const currentGeneration = ++generation
  anchor = target
  selectedOnly.value = showSelected
  const { vertical, verticalOffset } = verticalPlacement(
    anchor.getBoundingClientRect()
  )
  await context.value.show(anchor, vertical, 'left', verticalOffset)
  if (generation !== currentGeneration || !context.value?.isOpen()) return
  await updatePosition()
  if (generation !== currentGeneration || !context.value?.isOpen()) return
  cleanup()
  window.addEventListener('scroll', onScroll, true)
  window.addEventListener('resize', updatePosition)
  window.addEventListener('keyup', onKeyup)
}

onBeforeUnmount(() => {
  generation++
  cleanup()
})

defineExpose({ show })
</script>
