<template>
  <div class="decorator-list">
    <div
      v-for="(decoratorType, index) in viewDecoratorTypes"
      :key="decoratorType.getType()"
      v-tooltip="getTooltip(decoratorType)"
      class="decorator-list__item"
      :class="{ 'decorator-list__item--disabled': isDisabled(decoratorType) }"
      @click="addDecoration(decoratorType, index)"
    >
      <ViewDecoratorItem
        :deactivated="isDeactivated(decoratorType)"
        :decorator-type="decoratorType"
      />
      <component
        :is="decoratorType.getDeactivatedClickModal()[0]"
        v-if="decoratorType.getDeactivatedClickModal() !== null"
        :ref="'deactivatedClickModal' + index.toString()"
        v-bind="decoratorType.getDeactivatedClickModal()[1]"
        :name="decoratorType.getName()"
        :workspace="database.workspace"
      ></component>
    </div>
  </div>
</template>

<script>
import ViewDecoratorItem from '@baserow/modules/database/components/view/ViewDecoratorItem.vue'

export default {
  name: 'ViewDecoratorList',
  components: { ViewDecoratorItem },
  props: {
    database: {
      type: Object,
      required: true,
    },
    view: {
      type: Object,
      required: true,
    },
  },
  computed: {
    viewDecoratorTypes() {
      return this.$registry
        .getOrderedList('viewDecorator')
        .filter((deco) => deco.isCompatible(this.view))
    },
  },
  methods: {
    isDeactivated(decoratorType) {
      return decoratorType.isDeactivated(this.database.workspace.id)
    },
    isDisabled(decoratorType) {
      return !decoratorType.canAdd({ view: this.view })[0]
    },
    getTooltip(decoratorType) {
      const [canAdd, disabledReason] = decoratorType.canAdd({ view: this.view })
      if (!canAdd) {
        return disabledReason
      }
      if (this.isDeactivated(decoratorType)) {
        return decoratorType.getDeactivatedText()
      }
      return ''
    },
    addDecoration(decoratorType, index) {
      if (this.isDisabled(decoratorType)) {
        return
      } else if (this.isDeactivated(decoratorType)) {
        if (decoratorType.getDeactivatedClickModal() !== null) {
          this.$refs['deactivatedClickModal' + index.toString()][0].show()
        }
        return
      }
      this.$emit('select', decoratorType)
    },
  },
}
</script>
