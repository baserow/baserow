<template>
  <Context
    ref="context"
    class="variables-context"
    overflow-scroll
    max-height-if-outside-viewport
  >
    <div style="padding: 5px">{{ $t('common.comingSoon') }}</div>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'

export default {
  name: 'VariablesContext',
  mixins: [context],
  data() {
    return {}
  },
}
</script>
