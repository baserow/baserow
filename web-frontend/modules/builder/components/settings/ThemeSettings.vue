<template>
  <ThemeProvider class="theme-settings">
    <Tabs no-padding>
      <Tab
        v-for="themeConfigBlock in themeConfigBlocks"
        :key="themeConfigBlock.getType()"
        :title="themeConfigBlock.label"
      >
        <div class="padding-top-2">
          <ThemeConfigBlock
            ref="themeConfigBlocks"
            :default-values="builder.theme"
            :theme-config-block-type="themeConfigBlock"
            @values-changed="update($event)"
          />
        </div>
      </Tab>
    </Tabs>
  </ThemeProvider>
</template>

<script>
import ThemeProvider from '@baserow/modules/builder/components/theme/ThemeProvider'
import ThemeConfigBlock from '@baserow/modules/builder/components/theme/ThemeConfigBlock'

import { mapActions } from 'vuex'
import { notifyIf } from '@baserow/modules/core/utils/error'
import _ from 'lodash'

export default {
  name: 'ThemeSettings',
  components: { ThemeProvider, ThemeConfigBlock },
  provide() {
    return { builder: this.builder, mode: 'edit' }
  },
  props: {
    builder: {
      type: Object,
      required: true,
    },
  },
  computed: {
    themeConfigBlocks() {
      return this.$registry.getOrderedList('themeConfigBlock')
    },
  },
  methods: {
    ...mapActions({
      setThemeProperty: 'theme/setProperty',
      forceSetThemeProperty: 'theme/forceSetProperty',
    }),
    async update(newValues) {
      const differences = Object.fromEntries(
        Object.entries(newValues).filter(
          ([key, value]) => !_.isEqual(value, this.builder.theme[key])
        )
      )
      try {
        await Promise.all(
          Object.entries(differences).map(([key, value]) =>
            this.setThemeProperty({ builder: this.builder, key, value })
          )
        )
      } catch (error) {
        this.$refs.themeConfigBlocks.forEach((themeConfigBlock) =>
          themeConfigBlock.reset()
        )
        notifyIf(error, 'application')
      }
    },
    getTitle() {
      return ''
    },
  },
}
</script>
