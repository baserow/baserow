<template>
  <aside class="side-panels">
    <Tabs :key="element?.id" full-height>
      <Tab
        v-for="pageSidePanelType in pageSidePanelTypes"
        :key="pageSidePanelType.getType()"
        :tooltip="getTooltipMessage(pageSidePanelType)"
        tooltip-position="bottom-left"
        :title="pageSidePanelType.label"
        :append-icon="
          pageSidePanelType.isInError(sidePanelContext)
            ? 'page-editor__side-panel--error iconoir-warning-circle'
            : null
        "
        :disabled="!element || pageSidePanelType.isDeactivated(element)"
        :highlight="`builder-panel-${pageSidePanelType.getType()}`"
      >
        <ReadOnlyForm
          v-if="element"
          :read-only="
            !$hasPermission(
              'builder.page.element.update',
              element,
              workspace.id
            )
          "
        >
          <component
            :is="pageSidePanelType.component"
            :class="`side-panels__panel side-panels__panel-${pageSidePanelType.type}`"
          />
        </ReadOnlyForm>
        <EmptySidePanelState v-else />
      </Tab>
    </Tabs>
  </aside>
</template>

<script>
import { mapGetters } from 'vuex'
import EmptySidePanelState from '@baserow/modules/builder/components/page/sidePanels/EmptySidePanelState'

export default {
  name: 'PageSidePanels',
  components: { EmptySidePanelState },
  inject: ['workspace', 'builder'],
  computed: {
    ...mapGetters({
      getElementSelected: 'element/getSelected',
    }),
    element() {
      return this.getElementSelected(this.builder)
    },
    pageSidePanelTypes() {
      return this.$registry.getOrderedList('pageSidePanel')
    },
    sidePanelContext() {
      if (!this.element) {
        return { builder: this.builder }
      }
      const page = this.$store.getters['page/getById'](
        this.builder,
        this.element.page_id
      )
      return {
        page,
        builder: this.builder,
        element: this.element,
      }
    },
  },
  methods: {
    getTooltipMessage(pageSidePanelType) {
      if (this.element && pageSidePanelType.isDeactivated(this.element)) {
        return pageSidePanelType.getDeactivatedText()
      } else if (pageSidePanelType.isInError(this.sidePanelContext)) {
        return pageSidePanelType.getErrorMessage(this.sidePanelContext)
      }
      return null
    },
  },
}
</script>
