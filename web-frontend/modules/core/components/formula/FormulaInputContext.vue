<template>
  <Context ref="context" class="formula-input-context">
    <Tabs
      v-if="totalVisibleTabs > 1"
      :key="advanced ? 'advanced' : 'simple'"
      :selected-index="activeTabIndex"
      content-no-padding
      rounded
      @update:selectedIndex="activeTabIndex = $event"
    >
      <Tab :title="$t('formulaInputContext.variables')">
        <DataExplorer
          :nodes="dataExplorerNodes"
          :node-selected="nodeSelected"
          :loading="dataExplorerLoading"
          @node-selected="$emit('node-selected', $event)"
          @node-unselected="$emit('node-unselected')"
        />
      </Tab>

      <Tab
        v-for="tab in filteredTabs"
        :key="tab.name"
        :title="getTabTitle(tab.name)"
      >
        <SelectSearch
          v-model="searchQuery"
          :placeholder="$t('action.search')"
          class="margin-bottom-1"
        />

        <div class="formula-input-context__tab-content">
          <div v-if="tab.categories" class="formula-input-context__section">
            <div v-for="category in tab.categories" :key="category.name">
              <h4 class="formula-input-context__section-title">
                {{ category.name }}
              </h4>
              <ul class="formula-input-context__items">
                <li
                  v-for="item in getFilteredItems(category.items, tab.name)"
                  :key="item.name"
                  class="formula-input-context__item"
                  @click="insertItem(item, tab.name)"
                  @mouseenter="onFunctionHover(item, tab.name, $event)"
                  @mouseleave="onFunctionLeave"
                >
                  <i
                    :class="item.icon"
                    class="formula-input-context__item-icon"
                  ></i>

                  {{ item.name }}
                </li>
              </ul>
            </div>
          </div>

          <div v-else class="formula-input-context__section">
            <h4 class="formula-input-context__section-title">
              {{ getTabTitle(tab.name) }}
            </h4>
            <div class="formula-input-context__items">
              <div
                v-for="item in getFilteredItems(tab.items, tab.name)"
                :key="item.name"
                class="formula-input-context__item"
                @click="insertItem(item, tab.name)"
                @mouseenter="onFunctionHover(item, tab.name, $event)"
                @mouseleave="onFunctionLeave"
              >
                <i
                  :class="item.icon"
                  class="formula-input-context__item-icon"
                ></i>
                <div class="formula-input-context__item-content">
                  <div class="formula-input-context__item-name">
                    {{ item.name }}
                  </div>
                  <div
                    v-if="item.description"
                    class="formula-input-context__item-description"
                  >
                    {{ item.description }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Tab>
    </Tabs>

    <div v-else class="formula-input-context__single-tab-content">
      <DataExplorer
        :nodes="dataExplorerNodes"
        :node-selected="nodeSelected"
        :loading="dataExplorerLoading"
        @node-selected="$emit('node-selected', $event)"
        @node-unselected="$emit('node-unselected')"
      />
    </div>

    <div class="formula-input-context__footer">
      <ButtonText
        type="primary"
        icon="iconoir-input-field"
        size="small"
        @click="toggleAdvancedMode"
        >{{
          advanced
            ? $t('formulaInputContext.useRegularInput')
            : $t('formulaInputContext.useAdvancedInput')
        }}</ButtonText
      >
    </div>

    <FormulaFunctionHelpTooltip
      ref="functionHelpTooltip"
      :function-data="tooltip.functionData"
      :context-tabs="contextTabs"
    />

    <Modal ref="advancedModeModal" :title="modalTitle">
      <h2 class="box__title">
        {{
          advanced
            ? $t('formulaInputContext.useAdvancedInputModalTitle')
            : $t('formulaInputContext.useRegularInputModalTitle')
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
              advanced
                ? $t('formulaInputContext.useRegularInput')
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
import SelectSearch from '@baserow/modules/core/components/SelectSearch'
import DataExplorer from '@baserow/modules/core/components/dataExplorer/DataExplorer'
import Tab from '@baserow/modules/core/components/Tab'
import FormulaFunctionHelpTooltip from '@baserow/modules/core/components/formula/FormulaFunctionHelpTooltip'

export default {
  name: 'FormulaInputContext',
  components: {
    DataExplorer,
    Tab,
    SelectSearch,
    FormulaFunctionHelpTooltip,
  },
  mixins: [context],
  inject: ['contextTabs'],
  props: {
    nodeSelected: {
      type: String,
      required: false,
      default: null,
    },
    dataExplorerLoading: {
      type: Boolean,
      required: false,
      default: false,
    },
    dataProviders: {
      type: Array,
      required: false,
      default: () => [],
    },
    applicationContext: {
      type: Object,
      required: false,
      default: () => {},
    },
    advanced: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      activeTabIndex: 0,
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
    totalVisibleTabs() {
      return 1 + this.filteredTabs.length
    },
    dataExplorerNodes() {
      return this.dataProviders
        .map((dataProvider) => dataProvider.getNodes(this.applicationContext))
        .filter((dataProviderNodes) => dataProviderNodes.nodes?.length > 0)
    },
    functions() {
      const allItems = []

      this.tabs.forEach((tab) => {
        if (tab.categories) {
          tab.categories.forEach((category) => {
            if (category.items) {
              category.items.forEach((item) => {
                allItems.push({
                  ...item,
                  value: item.name,
                  operator: item.operator || null,
                  icon: item.icon || null,
                })
              })
            }
          })
        }
      })

      return allItems
    },
    functionNames() {
      const functionsTab = this.tabs.find((tab) => tab.name === 'Functions')
      if (!functionsTab || !functionsTab.categories) return []

      const functionNames = []

      functionsTab.categories.forEach((category) => {
        if (category.items) {
          category.items.forEach((item) => {
            functionNames.push(item.name)
          })
        }
      })

      return functionNames
    },
    operators() {
      const operatorsTab = this.tabs.find((tab) => tab.name === 'Operators')
      if (!operatorsTab || !operatorsTab.categories) return []

      const operators = []

      operatorsTab.categories.forEach((category) => {
        if (category.items) {
          category.items.forEach((item) => {
            if (item.operator) {
              operators.push({
                ...item,
                value: item.name,
                icon: item.icon,
              })
            }
          })
        }
      })

      return operators
    },
    filteredTabs() {
      if (!this.advanced) {
        return []
      }

      return this.tabs.filter((tab) => {
        if (tab.categories && tab.categories.length > 0) {
          return tab.categories.some(
            (category) => category.items && category.items.length > 0
          )
        }

        return false
      })
    },
  },
  watch: {
    advanced() {
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
    this.tabs = this.contextTabs
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
    insertItem(item, tabName) {
      if (tabName === 'Functions') {
        this.$emit('function-selected', item)
      } else if (tabName === 'Operators') {
        this.$emit('operator-selected', item)
      }
    },
    insertFunction(func) {
      this.$emit('function-selected', func)
    },
    insertOperator(operator) {
      this.$emit('operator-selected', operator)
    },
    toggleAdvancedMode() {
      if (this.advanced) {
        this.showAdvancedModeModal()
      } else {
        this.$emit('toggle-advanced-mode')
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
      this.$emit('toggle-advanced-mode')
      this.$refs.advancedModeModal.hide()
    },
    cancelModeChange() {
      this.$refs.advancedModeModal.hide()
    },
  },
}
</script>
