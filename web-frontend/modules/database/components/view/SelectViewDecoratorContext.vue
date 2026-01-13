<template>
  <Context ref="context" overflow-scroll max-height-if-outside-viewport>
    <ViewDecoratorList
      :database="database"
      :view="view"
      @select="$emit('select', $event)"
    />
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'
import ViewDecoratorList from '@baserow/modules/database/components/view/ViewDecoratorList'

export default {
  name: 'AddViewDecoratorContext',
  components: {
    ViewDecoratorList,
  },
  mixins: [context],
  props: {
    database: {
      type: Object,
      required: true,
    },
    view: {
      type: Object,
      required: true,
    },
  },
  emits: ['select'],
}
</script>
