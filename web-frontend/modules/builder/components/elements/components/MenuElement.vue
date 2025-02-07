<template>
  <div class="menu-element" :style="getStyleOverride(element.variant)">
    Menu Element!
  </div>
</template>

<script>
import element from '@baserow/modules/builder/mixins/element'
import resolveElementUrl from '@baserow/modules/builder/utils/urlResolution'
import { ensureString } from '@baserow/modules/core/utils/validator'

/**
 * @typedef MenuElement
 */

export default {
  name: 'MenuElement',
  mixins: [element],
  props: {
    /**
     * @type {MenuElement}
     */
    element: {
      type: Object,
      required: true,
    },
  },
  computed: {},
}
</script>
