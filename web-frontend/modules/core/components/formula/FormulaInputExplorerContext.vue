<template>
  <Context
    ref="context"
    class="formula-input-explorer-context"
    max-height-if-outside-viewport
    overflow-scroll
    data-formula-input-context
    :hide-on-click-outside="false"
  >
    <NodeExplorer
      :node-selected="nodeSelected"
      :mode="mode"
      :nodes-hierarchy="nodesHierarchy"
      :allow-node-selection="allowNodeSelection"
      :loading="loading"
      @node-selected="$emit('node-selected', $event)"
      @node-unselected="$emit('node-unselected')"
      @example-click="$emit('example-click', $event)"
    />
    <div v-if="showFooter" class="formula-input-explorer-context__footer">
      <ButtonText
        v-if="advancedModeEnabled"
        type="primary"
        icon="iconoir-input-field"
        size="small"
        @click="toggleMode"
        >{{
          isAdvancedMode
            ? $t('formulaInputExplorerContext.useSimpleInput')
            : $t('formulaInputExplorerContext.useAdvancedInput')
        }}</ButtonText
      >
      <div
        v-if="formatPickerEnabled"
        class="formula-input-explorer-context__format"
        role="group"
        :aria-label="$t('formulaInputExplorerContext.formatLabel')"
      >
        <SegmentControl
          size="small"
          :segments="formatSegments"
          :active-index="activeFormatIndex"
          @update:active-index="changeFormat"
        ></SegmentControl>
      </div>
    </div>

    <FormulaInputModeChangeModal
      ref="advancedModeModal"
      :title="
        isAdvancedMode
          ? $t('formulaInputExplorerContext.useSimpleInputModalTitle')
          : $t('formulaInputExplorerContext.useAdvancedInputModalTitle')
      "
      :confirm-label="
        isAdvancedMode
          ? $t('formulaInputExplorerContext.useSimpleInput')
          : $t('formulaInputExplorerContext.useAdvancedInput')
      "
      @confirm="confirmModeChange"
    />
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'
import NodeExplorer from '@baserow/modules/core/components/nodeExplorer/NodeExplorer'
import FormulaInputModeChangeModal from '@baserow/modules/core/components/formula/FormulaInputModeChangeModal'
import {
  BASEROW_FORMULA_MODES,
  BASEROW_FORMULA_FORMAT_PLAIN,
} from '@baserow/modules/core/formula/constants'

export default {
  name: 'FormulaInputExplorerContext',
  components: {
    NodeExplorer,
    FormulaInputModeChangeModal,
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
      type: String,
      required: false,
      default: 'none',
      validator: (value) => ['none', 'all', 'array', 'object'].includes(value),
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
    /**
     * The format the surface renders the resolved formula in.
     */
    format: {
      type: String,
      required: false,
      default: BASEROW_FORMULA_FORMAT_PLAIN,
    },
    /**
     * The `{ value, name }` formats the surface can render. The format picker
     * in the footer only shows when there is more than one.
     */
    formatOptions: {
      type: Array,
      required: false,
      default: () => [],
    },
  },
  emits: [
    'mode-changed',
    'format-changed',
    'node-selected',
    'node-unselected',
    'example-click',
  ],
  data() {
    return {
      searchQuery: '',
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
    formatPickerEnabled() {
      return this.formatOptions.length > 1
    },
    showFooter() {
      return this.advancedModeEnabled || this.formatPickerEnabled
    },
    formatSegments() {
      return this.formatOptions.map(({ name }) => ({ label: name }))
    },
    activeFormatIndex() {
      const index = this.formatOptions.findIndex(
        ({ value }) => value === this.format
      )
      return index === -1 ? 0 : index
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
    },
    getTabTitle(tabName) {
      const titleMap = {
        Functions: this.$t('formulaInputExplorerContext.functions'),
        Operators: this.$t('formulaInputExplorerContext.operators'),
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
    showAdvancedModeModal() {
      this.$refs.advancedModeModal.show()
    },
    confirmModeChange() {
      this.$emit(
        'mode-changed',
        this.mode === 'advanced' ? 'simple' : 'advanced'
      )
    },
    changeFormat(index) {
      const option = this.formatOptions[index]
      if (option && option.value !== this.format) {
        this.$emit('format-changed', option.value)
      }
    },
  },
}
</script>
