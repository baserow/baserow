<template>
  <Context
    ref="context"
    class="formula-input-context"
    max-height-if-outside-viewport
    overflow-scroll
  >
    <NodeExplorer
      :node-selected="nodeSelected"
      :mode="mode"
      :nodes-hierarchy="nodesHierarchy"
      :allow-node-selection="allowNodeSelection"
      :loading="loading"
      @node-selected="$emit('node-selected', $event)"
      @node-unselected="$emit('node-unselected')"
    />
    <div v-if="advancedModeEnabled" class="formula-input-context__footer">
      <ButtonText
        type="primary"
        icon="iconoir-input-field"
        size="small"
        @click="toggleMode"
        >{{
          isAdvancedMode
            ? $t('formulaInputContext.useSimpleInput')
            : $t('formulaInputContext.useAdvancedInput')
        }}</ButtonText
      >
    </div>

    <Modal ref="advancedModeModal">
      <h2 class="box__title">
        {{
          isAdvancedMode
            ? $t('formulaInputContext.useSimpleInputModalTitle')
            : $t('formulaInputContext.useAdvancedInputModalTitle')
        }}
      </h2>
      <p>{{ $t('formulaInputContext.modalMessage') }}</p>

      <div class="actions margin-bottom-0">
        <div class="align-right">
          <Button type="secondary" size="large" @click="cancelModeChange">
            {{ $t('action.cancel') }}
          </Button>
          <Button type="danger" size="large" @click="confirmModeChange">
            {{
              isAdvancedMode
                ? $t('formulaInputContext.useSimpleInput')
                : $t('formulaInputContext.useAdvancedInput')
            }}
          </Button>
        </div>
      </div>
    </Modal>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'
import NodeExplorer from '@baserow/modules/core/components/nodeExplorer/NodeExplorer'
import { BASEROW_FORMULA_MODES } from '@baserow/modules/core/formula/constants'

export default {
  name: 'FormulaInputContext',
  components: {
    NodeExplorer,
  },
  mixins: [context],
  props: {
    nodeSelected: {
      type: String,
      required: false,
      default: null,
    },
    nodesHierarchy: {
      type: Array,
      required: false,
      default: () => [],
    },
    loading: {
      type: Boolean,
      required: false,
      default: false,
    },
    mode: {
      type: String,
      required: false,
      default: 'advanced',
      validator: (value) => {
        return BASEROW_FORMULA_MODES.includes(value)
      },
    },
    /**
     * Whether the formula input has a formula value set or not.
     * Used to determine if we need to show a confirmation prompt
     * or not when the mode changes from advanced to simple.
     */
    hasValue: {
      type: Boolean,
      required: false,
      default: false,
    },
    allowNodeSelection: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * An array of Baserow formula modes which the parent formula input
     * component allows to be used. By default, in `FormulaInputField`,
     * we will allow all modes.
     */
    enabledModes: {
      type: Array,
      required: true,
    },
  },
  data() {
    return {
      searchQuery: '',
      tooltip: {
        functionData: null,
      },
      tooltipTimer: null,
      tabs: [],
      isModalVisible: false,
    }
  },
  computed: {
    advancedModeEnabled() {
      return this.enabledModes.includes('advanced')
    },
    isAdvancedMode() {
      return this.mode === 'advanced'
    },
  },
  watch: {
    mode() {
      this.$nextTick(() => {
        this.activeTabIndex = 0
      })
    },
    activeTabIndex() {
      this.searchQuery = ''
      this.hideTooltip()
    },
  },
  created() {
    this.tabs = this.nodes
  },
  methods: {
    show(
      targetElement,
      verticalPosition = 'bottom',
      horizontalPosition = 'left',
      verticalOffset = 0,
      horizontalOffset = 0
    ) {
      return this.$refs.context.show(
        targetElement,
        verticalPosition,
        horizontalPosition,
        verticalOffset,
        horizontalOffset
      )
    },
    hide() {
      this.$refs.context.hide()
      this.hideTooltip()
    },
    getTabTitle(tabName) {
      const titleMap = {
        Functions: this.$t('formulaInputContext.functions'),
        Operators: this.$t('formulaInputContext.operators'),
      }
      return titleMap[tabName] || tabName
    },

    getFilteredItems(items, tabName) {
      if (!items || !this.searchQuery) {
        return items || []
      }

      return items.filter(
        (item) =>
          item.name.toLowerCase().includes(this.searchQuery.toLowerCase()) ||
          (item.description &&
            item.description
              .toLowerCase()
              .includes(this.searchQuery.toLowerCase()))
      )
    },
    toggleMode() {
      if (this.mode === 'advanced') {
        if (this.hasValue) {
          // If we have a value then we want the user to confirm
          // they're happy for the formula to be reset.
          this.showAdvancedModeModal()
        } else {
          // If we have no value then we can safely switch modes.
          this.$emit('mode-changed', 'simple')
        }
      } else {
        this.$emit('mode-changed', 'advanced')
      }
    },
    onFunctionHover(item, tabName, event) {
      if (tabName !== 'Functions') {
        return
      }

      if (this.tooltipTimer) {
        clearTimeout(this.tooltipTimer)
      }

      this.tooltip.functionData = {
        name: item.name,
        description: item.description,
        example: item.example,
        icon: item.icon,
      }

      this.tooltipTimer = setTimeout(() => {
        if (this.$refs.functionHelpTooltip) {
          this.$refs.functionHelpTooltip.show(
            event.target,
            'bottom',
            'right',
            5,
            10
          )
        }
      }, 300)
    },
    onFunctionLeave() {
      if (this.tooltipTimer) {
        clearTimeout(this.tooltipTimer)
        this.tooltipTimer = null
      }

      this.hideTooltip()
    },
    hideTooltip() {
      if (this.$refs.functionHelpTooltip) {
        this.$refs.functionHelpTooltip.hide()
      }
      this.tooltip.functionData = null
    },
    showAdvancedModeModal() {
      this.$refs.advancedModeModal.show()
    },
    confirmModeChange() {
      this.$emit(
        'mode-changed',
        this.mode === 'advanced' ? 'simple' : 'advanced'
      )
      this.$refs.advancedModeModal.hide()
    },
    cancelModeChange() {
      this.$refs.advancedModeModal.hide()
    },
  },
}
</script>
