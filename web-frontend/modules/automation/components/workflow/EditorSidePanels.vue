<template>
  <aside class="side-panels">
    <component :is="sidePanelType.component" />
  </aside>
</template>

<script>
import { useContext, computed } from '@nuxtjs/composition-api'
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'EditorSidePanels',
  props: {
    activeSidePanel: {
      type: String,
      required: false,
      default: () => null,
    },
  },
  setup(props) {
    const { app } = useContext()
    const sidePanelType = computed(() => {
      return props.activeSidePanel
        ? app.$registry.get('editorSidePanel', props.activeSidePanel)
        : null
    })
    return {
      sidePanelType,
    }
  },
})
</script>
