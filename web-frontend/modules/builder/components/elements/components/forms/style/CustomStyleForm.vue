<template>
  <div class="custom-style__form">
    <div class="custom-style__header" @click="$emit('hide', true)">
      <i class="custom-style__title-icon iconoir-nav-arrow-left" />
      <div class="custom-style__title">
        {{ $t('customStyle.backToElement') }}
      </div>
    </div>
    <Tabs class="custom-style__config-blocks">
      <Tab
        v-for="themeConfigBlock in themeConfigBlocks"
        :key="themeConfigBlock.getType()"
        :title="themeConfigBlock.label"
        class="custom-style__config-block"
      >
        <div class="custom-style__config-block-content">
          <ThemeConfigBlock
            ref="configBlocks"
            :preview="false"
            :theme="customStylesContext.theme"
            :default-values="customStylesContext.defaultStyleValues"
            :theme-config-block-type="themeConfigBlock"
            :extra-args="customStylesContext.extraArgs"
            @values-changed="$emit('values-changed', $event)"
          />
        </div>
      </Tab>
    </Tabs>
  </div>
</template>

<script>
import ThemeConfigBlock from '@baserow/modules/builder/components/theme/ThemeConfigBlock'

export default {
  name: 'CustomStyleForm',
  components: { ThemeConfigBlock },
  props: {
    /**
     * @type {Object}
     * @property {object} theme - The current theme object.
     * @property {string} styleKey - The key of the style being edited.
     * @property {object|null} extraArgs - Any extra args needed for the blocks.
     * @property {object} defaultStyleValues - The default values for the styles.
     * @property {Array<string>} configBlockTypes - The types of config blocks
     *  to render for this custom style form.
     */
    customStylesContext: {
      type: Object,
      required: true,
    },
  },
  computed: {
    themeConfigBlocks() {
      return this.customStylesContext.configBlockTypes.map((confType) =>
        this.$registry.get('themeConfigBlock', confType)
      )
    },
  },
  methods: {
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
