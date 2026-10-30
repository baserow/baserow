<template>
  <div class="grid-view__group-value-many-to-many">
    <div
      v-for="item in value"
      :key="item.id"
      class="grid-view__group-value-collaborator"
    >
      <!-- An optimistically-created group only knows the id; resolve the name from the
           store so a new group shows its badge before the server display arrives. -->
      <template v-if="item.id != null">
        <div class="grid-view__group-value-collaborator-name">
          <span class="grid-view__group-value-collaborator-name-text">{{
            getCollaboratorName(item, $store)
          }}</span>
        </div>
        <CollaboratorAvatar
            :field="field"
          class="grid-view__group-value-collaborator-initials"
          :collaborator="item"
        />
      </template>
    </div>
  </div>
</template>

<script>
import CollaboratorAvatar from '@baserow/modules/core/components/CollaboratorAvatar'
import collaboratorName from '@baserow/modules/database/mixins/collaboratorName'

export default {
  name: 'GridViewGroupValueMultipleCollaborators',
  components: { CollaboratorAvatar },
  mixins: [collaboratorName],
  props: {
    value: {
      type: Array,
      default: () => [],
    },
  },
}
</script>
