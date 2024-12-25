<template>
  <Context :overflow-scroll="true" :max-height-if-outside-viewport="true">
    <ul class="context__menu">
      <li class="context__menu-item">
        <a class="context__menu-item-link" @click="handleShareClick">
          <i class="context__menu-item-icon iconoir-copy"></i>
          {{
            shared
              ? $t('dataSourceItemContext.unshareBetweenPages')
              : $t('dataSourceItemContext.shareBetweenPages')
          }}
        </a>
        <a class="context__menu-item-link" @click="handleDeleteClick">
          <i class="context__menu-item-icon iconoir-bin"></i>
          {{ $t('action.delete') }}
        </a>
      </li>
    </ul>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'

export default {
  name: 'DataSourceItemContext',
  mixins: [context],
  props: {
    shared: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  methods: {
    handleDeleteClick() {
      this.$emit('delete')
      this.hide()
    },
    handleShareClick() {
      this.$emit('share')
      this.hide()
    },
  },
}
</script>
