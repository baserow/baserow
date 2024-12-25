<template>
  <div class="custom-style" :class="`custom-style--${variant}`">
    <ButtonText
      v-if="variant === 'float'"
      v-tooltip="$t('customStyle.configureThemeOverrides')"
      class="custom-style__button"
      icon="baserow-icon-settings"
      tooltip-position="bottom-left"
      @click="openPanel()"
    />
    <ButtonIcon
      v-else
      v-tooltip="$t('customStyle.configureThemeOverrides')"
      class="custom-style__button"
      icon="baserow-icon-settings"
      tooltip-position="bottom-left"
      @click="openPanel()"
    />
    <Context ref="context" class="custom-style__context">
      <div class="custom-style__header" @click="$refs.context.hide()">
        <i class="custom-style__title-icon iconoir-nav-arrow-left" />
        <div class="custom-style__title">
          {{ $t('customStyle.themeOverrides') }}
        </div>
      </div>
      <Tabs class="custom-style__config-blocks">
        <Tab
          v-for="themeConfigBlock in themeConfigBlocks"
          :key="themeConfigBlock.getType()"
          :title="themeConfigBlock.label"
          class="custom-style__config-block"
        >
          <div
            v-auto-overflow-scroll
            class="custom-style__config-block-content"
          >
            <ThemeConfigBlock
              ref="configBlocks"
              :theme="theme"
              :default-values="value?.[styleKey]"
              :preview="false"
              :theme-config-block-type="themeConfigBlock"
              :extra-args="extraArgs"
              @values-changed="onValuesChanged($event)"
            />
          </div>
        </Tab>
      </Tabs>
    </Context>
  </div>
</template>

<script>
import ThemeConfigBlock from '@baserow/modules/builder/components/theme/ThemeConfigBlock'
import { getParentMatchingPredicate } from '@baserow/modules/core/utils/dom'

export default {
  name: 'CustomStyle',
  components: { ThemeConfigBlock },
  props: {
    value: {
      type: Object,
      required: false,
      default: () => undefined,
    },
    variant: {
      required: false,
      type: String,
      default: 'float',
      validator: function (value) {
        return ['float', 'normal'].includes(value)
      },
    },
    theme: { type: Object, required: true },
    configBlockTypes: {
      type: Array,
      required: true,
    },
    styleKey: { type: String, required: true },
    extraArgs: {
      type: Object,
      required: false,
      default: () => null,
    },
  },
  data() {
    return {}
  },
  computed: {
    themeConfigBlocks() {
      return this.configBlockTypes.map((confType) =>
        this.$registry.get('themeConfigBlock', confType)
      )
    },
  },
  methods: {
    openPanel() {
      const sidePanel = getParentMatchingPredicate(this.$el, (el) =>
        el.classList.contains('page-editor__side-panel')
      )
      this.$refs.context.show(sidePanel, 'over', 'right', 0, 0)
    },
    onValuesChanged(newValues) {
      this.$emit('input', {
        ...this.value,
        [this.styleKey]: newValues,
      })
    },
    /**
     * With isFormValid and reset we mimic the form mixin API so the forms are reset
     * when an error happens during the update request.
     */
    isFormValid() {
      return (this.$refs.configBlocks || [])
        .map((confBlock) => confBlock.isFormValid())
        .every((v) => v)
    },
    async reset() {
      await this.$nextTick() // Wait the default value to be updated
      return (this.$refs.configBlocks || []).forEach((confBlock) =>
        confBlock.reset()
      )
    },
  },
}
</script>
