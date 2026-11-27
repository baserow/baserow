<template>
  <Context ref="context">
    <ul class="context__menu">
      <li v-if="canUpdate" class="context__menu-item">
        <a class="context__menu-item-link" @click.prevent="edit">
          <i class="context__menu-item-icon iconoir-edit-pencil"></i>
          {{ $t('workspaceIntegrations.edit') }}
        </a>
      </li>
      <li v-if="canPromote" class="context__menu-item">
        <a class="context__menu-item-link" @click.prevent="promote">
          <i class="context__menu-item-icon iconoir-share-android"></i>
          {{ $t('promoteIntegration.action') }}
        </a>
      </li>
      <li
        v-if="canDelete"
        class="context__menu-item"
        :class="{
          'context__menu-item--with-separator': canUpdate || canPromote,
        }"
      >
        <a
          class="context__menu-item-link context__menu-item-link--delete"
          @click.prevent="remove"
        >
          <i class="context__menu-item-icon iconoir-bin"></i>
          {{ $t('workspaceIntegrations.delete') }}
        </a>
      </li>
    </ul>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'

export default {
  name: 'WorkspaceIntegrationContext',
  mixins: [context],
  props: {
    canUpdate: { type: Boolean, required: true },
    canDelete: { type: Boolean, required: true },
    // Only for the integrations of an application, which can be made available
    // to the whole workspace.
    canPromote: { type: Boolean, default: false },
  },
  emits: ['edit', 'promote', 'delete'],
  methods: {
    edit() {
      this.hide()
      this.$emit('edit')
    },
    promote() {
      this.hide()
      this.$emit('promote')
    },
    // The workspace table asks for a confirmation, because every application
    // of the workspace that uses the integration loses it. Published
    // applications and workflows keep their own copy until they're published
    // again.
    remove() {
      this.hide()
      this.$emit('delete')
    },
  },
}
</script>
