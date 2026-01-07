<template>
  <Context ref="context" overflow-scroll max-height-if-outside-viewport>
    <ul class="context__menu">
      <li v-if="canBeEdited(authProvider.type)" class="context__menu-item">
        <a
          class="context__menu-item-link"
          @click="$emit('edit', authProvider.id)"
        >
          <i class="context__menu-item-icon iconoir-edit-pencil"></i>
          {{ $t('editAuthProviderMenuContext.edit') }}
        </a>
      </li>
      <li
        v-if="canBeDeleted(authProvider.type)"
        class="context__menu-item context__menu-item--with-separator"
      >
        <a
          class="context__menu-item-link context__menu-item-link--delete"
          @click="$emit('delete', authProvider.id)"
        >
          <i class="context__menu-item-icon iconoir-bin"></i>
          {{ $t('editAuthProviderMenuContext.delete') }}
        </a>
      </li>
      <slot></slot>
    </ul>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'
import authProviderItemMixin from '@baserow_enterprise/mixins/authProviderItemMixin'

export default {
  name: 'EditAuthProviderMenuContext',
  emits: ['delete', 'edit'],
  components: {},
  mixins: [context, authProviderItemMixin],
  props: {
    authProvider: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      deleteLoading: false,
    }
  },
}
</script>
