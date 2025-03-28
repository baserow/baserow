<template>
  <header class="layout__col-2-1 header header--space-between">
    <AutomationHeaderMenuItems :automation="automation" />
    <div>
      <!-- Add new... button -->
    </div>
  </header>
</template>

<script>
import AutomationHeaderMenuItems from '@baserow/modules/automation/components/AutomationHeaderMenuItems'

export default {
  name: 'AutomationHeader',
  components: {
    AutomationHeaderMenuItems,
  },
  props: {
    automation: {
      type: Object,
      required: true,
    },
  },
}
</script>
