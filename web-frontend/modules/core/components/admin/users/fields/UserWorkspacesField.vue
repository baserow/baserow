<template>
  <ExpandOnOverflowList
    ref="expandOnOverflow"
    :row="row"
    :column="column"
    :name-key="nameKey"
  >
    <template #icon="{ record }">
      <i
        v-if="record.permissions === 'ADMIN'"
        v-tooltip="$t('user.isWorkspaceAdmin')"
        class="user-admin-group__icon iconoir-user-crown"
      ></i>
    </template>
  </ExpandOnOverflowList>
</template>
<script>
import ExpandOnOverflowList from '@baserow/modules/core/components/crudTable/ExpandOnOverflowList'

/**
 * Displays a list of a workspaces with a modal displaying any workspaces that do not
 * fit.
 */
export default {
  name: 'UserWorkspacesField',
  components: {
    ExpandOnOverflowList,
  },
  props: {
    row: {
      required: true,
      type: Object,
    },
    column: {
      required: true,
      type: Object,
    },
  },
  data() {
    return {
      nameKey: 'name',
    }
  },
}
</script>
