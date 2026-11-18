<template>
  <Context ref="context">
    <ul class="context__menu">
      <li v-if="canUpdate" class="context__menu-item">
        <a class="context__menu-item-link" @click.prevent="edit">
          <i class="context__menu-item-icon iconoir-edit-pencil"></i>
          {{ $t('identities.edit') }}
        </a>
      </li>
      <li
        v-if="canDelete"
        class="context__menu-item"
        :class="{ 'context__menu-item--with-separator': canUpdate }"
      >
        <a
          class="context__menu-item-link context__menu-item-link--delete"
          @click.prevent="remove"
        >
          <i class="context__menu-item-icon iconoir-bin"></i>
          {{ $t('identities.delete') }}
        </a>
      </li>
    </ul>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'

export default {
  name: 'IdentityContext',
  mixins: [context],
  props: {
    identity: { type: Object, required: true },
    canUpdate: { type: Boolean, required: true },
    canDelete: { type: Boolean, required: true },
  },
  emits: ['edit', 'deleted'],
  methods: {
    edit() {
      this.hide()
      this.$emit('edit')
    },
    async remove() {
      await this.$store.dispatch('identity/delete', this.identity)
      // The store update can unmount this menu before the request resolves.
      if (this.$refs.context) this.hide()
      this.$emit('deleted', this.identity.id)
    },
  },
}
</script>
