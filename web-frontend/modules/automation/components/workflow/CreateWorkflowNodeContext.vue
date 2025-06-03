<template>
  <Context class="workflow_node_context">
    <Dropdown
      size="large"
      show-search
      open-on-mount
      :fixed-items="true"
      :show-input="false"
      :search-text="$t('createWorkflowNodeContext.searchPlaceholder')"
      @change="onChange"
    >
      <DropdownItem
        v-for="nodeType in nodeTypes"
        :key="nodeType.getType()"
        :name="nodeType.name"
        :image="nodeType.image"
        :value="nodeType.getType()"
        :description="nodeType.description"
      ></DropdownItem>
    </Dropdown>
  </Context>
</template>

<script>
import Context from '@baserow/modules/core/components/Context'
import { defineComponent, computed } from 'vue'
import { useContext } from '@nuxtjs/composition-api'

export default defineComponent({
  name: 'CreateWorkflowNodeContext',
  components: { Context },
  props: {
    lastNodeId: {
      type: [Number, String],
      required: false,
      default: null,
    },
    workflowHasTrigger: {
      type: Boolean,
      required: true,
    },
  },
  emits: ['change'],
  setup(props, { emit }) {
    const { app } = useContext()

    const onChange = (nodeType) => {
      emit('change', nodeType, props.lastNodeId)
    }

    const nodeTypes = computed(() => {
      return Object.values(app.$registry.getAll('node')).filter((nodeType) => {
        return props.workflowHasTrigger
          ? nodeType.isWorkflowAction
          : nodeType.isTrigger
      })
    })

    return {
      onChange,
      nodeTypes,
    }
  },
})
</script>
