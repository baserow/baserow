<template>
  <Context ref="context" overflow-scroll max-height-if-outside-viewport>
    <div>
      <ul class="context__menu">
        <li class="context__menu-item edit">
          <a
            class="context__menu-item-link"
            :class="{ disabled: !canEdit }"
            @click.prevent="editComment"
          >
            <i class="context__menu-item-icon iconoir-edit-pencil"></i>
            <span> {{ $t('rowCommentContext.edit') }} </span>
          </a>
        </li>
        <li class="context__menu-item context__menu-item--with-separator">
          <a
            class="context__menu-item-link context__menu-item-link--delete"
            :class="{ disabled: !canDelete }"
            @click.prevent="deleteComment"
          >
            <i class="context__menu-item-icon iconoir-bin"></i>
            <span> {{ $t('rowCommentContext.delete') }} </span>
          </a>
        </li>
      </ul>
    </div>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'

export default {
  name: 'RowCommentContext',
  emits: ['delete', 'edit'],
  mixins: [context],
  props: {
    canEdit: {
      type: Boolean,
      required: true,
    },
    canDelete: {
      type: Boolean,
      required: true,
    },
  },
  methods: {
    editComment() {
      if (this.canEdit) {
        this.$emit('edit')
      }
    },
    deleteComment() {
      if (this.canDelete) {
        this.$emit('delete')
      }
    },
  },
}
</script>
