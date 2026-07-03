<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      small-label
      :label="$t('coreGotoServiceForm.conditionLabel')"
      required
      class="margin-bottom-2"
    >
      <p class="margin-top-0 margin-bottom-1">
        {{ $t('coreGotoServiceForm.conditionDescription') }}
      </p>
      <InjectedFormulaInput
        v-model="values.condition"
        :placeholder="$t('coreGotoServiceForm.conditionPlaceholder')"
      />
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('coreGotoServiceForm.destinationLabel')"
      required
    >
      <p class="margin-top-0 margin-bottom-1">
        {{ $t('coreGotoServiceForm.destinationDescription') }}
      </p>
      <Dropdown
        v-model="values.destination_node_id"
        :placeholder="$t('coreGotoServiceForm.destinationPlaceholder')"
      >
        <DropdownItem
          v-for="destination in destinationNodes"
          :key="destination.id"
          :name="getNodeName(destination)"
          :value="destination.id"
        />
      </Dropdown>
    </FormGroup>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import { isValidGotoDestination } from '@baserow/modules/automation/utils/gotoNode'

export default {
  name: 'CoreGotoServiceForm',
  components: { InjectedFormulaInput },
  mixins: [form],
  inject: ['applicationContext'],
  props: {
    service: {
      type: Object,
      required: false,
      default: null,
    },
  },
  data() {
    return {
      allowedValues: ['condition', 'destination_node_id'],
      values: {
        condition: {},
        destination_node_id: null,
      },
    }
  },
  computed: {
    currentNode() {
      return this.applicationContext.node
    },
    automation() {
      return this.applicationContext.automation
    },
    workflow() {
      return this.applicationContext.workflow
    },
    /**
     * The eligible destination nodes are the valid backward-jump targets for
     * the current "Go to node": non-trigger, same-level nodes of the workflow
     * that run before it (see `isValidGotoDestination`, which mirrors the
     * backend `validate_goto_destination`).
     */
    destinationNodes() {
      const nodes = this.$store.getters['automationWorkflowNode/getNodes'](
        this.workflow
      )
      return nodes.filter((node) =>
        isValidGotoDestination({
          gotoNode: this.currentNode,
          destinationNode: node,
          ancestorsOf: (n) =>
            this.$store.getters['automationWorkflowNode/getAncestors'](
              this.workflow,
              n
            ),
          previousNodesOf: (n) =>
            this.$store.getters['automationWorkflowNode/getPreviousNodes'](
              this.workflow,
              n
            ),
          isTrigger: (n) => this.$registry.get('node', n.type).isTrigger,
        })
      )
    },
  },
  watch: {
    /**
     * The `form` mixin seeds `values` from `defaultValues` only once, so an
     * external change to the destination (e.g. a move clears the link because
     * it became a forward jump) wouldn't otherwise reach the dropdown. Adopt
     * such changes here.
     */
    service(service) {
      const destinationNodeId = service?.destination_node_id ?? null
      if (destinationNodeId !== this.values.destination_node_id) {
        this.values.destination_node_id = destinationNodeId
      }
    },
  },
  methods: {
    getNodeName(node) {
      const nodeType = this.$registry.get('node', node.type)
      return (
        node.label ||
        nodeType.getDefaultLabel({ automation: this.automation, node })
      )
    },
  },
}
</script>
