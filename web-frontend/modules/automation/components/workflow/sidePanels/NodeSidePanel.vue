<template>
  <ReadOnlyForm
    v-if="node"
    :read-only="
      workflowReadOnly ||
      !$hasPermission('automation.node.update', node, workspace.id)
    "
  >
    <FormGroup
      class="margin-bottom-1"
      :label="$t('nodeSidePanel.labelTitle')"
      :error="v$.label.$error"
      :error-message="v$.label.$errors[0]?.$message"
      small-label
    >
      <FormInput
        :value="values.label"
        :placeholder="nodeType.getDefaultLabel({ automation, node })"
        :error="v$.label.$error"
        @input="handleNodeChange({ node: { label: $event } })"
      />
    </FormGroup>
    <component
      :is="nodeType.formComponent"
      :key="node.id"
      small
      :loading="nodeLoading"
      :service="node.service"
      :application="automation"
      enable-integration-picker
      :default-values="node.service"
      class="margin-top-2"
      @values-changed="handleNodeChange({ service: $event })"
    />
  </ReadOnlyForm>
</template>

<script setup>
import {
  inject,
  provide,
  useStore,
  useContext,
  computed,
  watch,
} from '@nuxtjs/composition-api'
import { reactive } from 'vue'
import useVuelidate from '@vuelidate/core'
import ReadOnlyForm from '@baserow/modules/core/components/ReadOnlyForm'
import AutomationBuilderFormulaInput from '@baserow/modules/automation/components/AutomationBuilderFormulaInput'
import { DATA_PROVIDERS_ALLOWED_NODE_ACTIONS } from '@baserow/modules/automation/enums'
import _ from 'lodash'
import { helpers, maxLength } from '@vuelidate/validators'

const store = useStore()
const { app } = useContext()

provide('formulaComponent', AutomationBuilderFormulaInput)
provide('dataProvidersAllowed', DATA_PROVIDERS_ALLOWED_NODE_ACTIONS)

const workspace = inject('workspace')
const automation = inject('automation')
const workflow = inject('workflow')
const workflowReadOnly = inject('workflowReadOnly')

const node = computed(() => {
  return store.getters['automationWorkflowNode/getSelected'](workflow.value)
})

const values = reactive({
  label: '',
})
watch(
  node,
  (newNode) => {
    if (newNode) {
      values.label = newNode.label || ''
    }
  },
  { immediate: true }
)
const rules = {
  label: {
    maxLength: helpers.withMessage(
      app.i18n.t('error.maxLength', { max: 75 }),
      maxLength(75)
    ),
  },
}
const v$ = useVuelidate(rules, values, { $lazy: true })

/**
 * The application context is provided as a reactive object
 * as the `node` (the selected node) will change. If it's not
 * reactive, the components that consume this context will not
 * update when the node changes.
 */
const applicationContext = reactive({
  get node() {
    return node.value
  },
  get automation() {
    return automation.value
  },
  get workflow() {
    return workflow.value
  },
})
provide('applicationContext', applicationContext)

const nodeType = computed(() => {
  return app.$registry.get('node', node.value.type)
})

const handleNodeChange = async ({
  node: nodeChanges,
  service: serviceChanges,
}) => {
  let updatedNode = { ...node.value }
  let anyChanges = false

  // Handle node changes first
  if (nodeChanges) {
    // Do we have a new label? If we do, validate it.
    if (nodeChanges.label !== undefined) {
      values.label = nodeChanges.label
      v$.value.$touch()
      if (v$.value.$invalid) {
        return
      }
    }

    const nodeDifferences = Object.fromEntries(
      Object.entries(nodeChanges).filter(
        ([key, value]) => !_.isEqual(value, node.value[key])
      )
    )

    if (Object.keys(nodeDifferences).length > 0) {
      updatedNode = { ...updatedNode, ...nodeDifferences }
      anyChanges = true
    }
  }

  // Handle service changes next
  if (serviceChanges) {
    const serviceDifferences = Object.fromEntries(
      Object.entries(serviceChanges).filter(
        ([key, value]) => !_.isEqual(value, node.value.service[key])
      )
    )

    if (Object.keys(serviceDifferences).length > 0) {
      updatedNode.service = { ...updatedNode.service, ...serviceDifferences }
      anyChanges = true
    }
  }

  // Early return if nothing has changed
  if (!anyChanges) {
    return
  }

  await store.dispatch('automationWorkflowNode/updateDebounced', {
    workflow: workflow.value,
    node: node.value,
    values: updatedNode,
  })
}

const nodeLoading = computed(() => {
  return store.getters['automationWorkflowNode/getLoading'](node.value)
})
</script>
