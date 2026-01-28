<template>
  <Context ref="context" overflow-scroll max-height-if-outside-viewport>
    <div class="context__menu-title">
      {{ $t('gridViewRowsAddContext.title') }}
    </div>
    <ul class="context__menu">
      <li
        v-for="rowAmountChoice in rowAmountChoices"
        :key="rowAmountChoice"
        class="context__menu-item"
      >
        <a
          class="context__menu-item-link"
          @click="$emit('add-rows', rowAmountChoice)"
        >
          {{ $t('gridViewRowsAddContext.choice', { rowAmountChoice }) }}
        </a>
      </li>
    </ul>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'

export default {
  name: 'GridViewRowsAddContext',
  mixins: [context],
  emits: ['add-rows'],
  computed: {
    rowAmountChoices() {
      return [5, 10, 20, 50]
    },
  },
}
</script>
