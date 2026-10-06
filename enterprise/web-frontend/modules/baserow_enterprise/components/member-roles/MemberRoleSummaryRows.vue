<template>
  <tr class="data-table__table-row member-role-summary">
    <td :colspan="roleColumnIndex" class="data-table__table-cell">
      <div class="data-table__table-cell-content">
        <div>
          <div>
            {{
              $t('memberRoleSummary.highestRole', { workspace: workspace.name })
            }}
          </div>
          <div class="member-role-summary__description">
            {{ $t('memberRoleSummary.description') }}
          </div>
        </div>
      </div>
    </td>
    <td class="data-table__table-cell">
      <div class="data-table__table-cell-content">
        <Badge>
          {{ roleName }}
        </Badge>
      </div>
    </td>
    <td
      v-for="column in columns.slice(roleColumnIndex + 1)"
      :key="column.key"
      class="data-table__table-cell"
      :class="{ 'data-table__table-cell--sticky-right': column.stickyRight }"
    />
  </tr>
</template>

<script setup>
import { computed } from 'vue'
import Badge from '@baserow/modules/core/components/Badge'

const props = defineProps({
  member: { type: Object, required: true },
  columns: { type: Array, required: true },
  workspace: { type: Object, required: true },
})
const roleColumnIndex = computed(() =>
  props.columns.findIndex((column) => column.key === 'role_uid')
)
const roleName = computed(
  () =>
    props.workspace._.roles.find(
      (role) => role.uid === props.member.highest_role_uid
    )?.name || props.member.highest_role_uid
)
</script>
