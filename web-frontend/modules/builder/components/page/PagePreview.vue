<template>
  <div
    class="page-preview__wrapper"
    :class="`page-preview__wrapper--${deviceType.type}`"
    @click.self="actionSelectElement({ builder, element: null })"
  >
    <PreviewNavigationBar :page="currentPage" :style="{ maxWidth }" />
    <div ref="preview" class="page-preview" :style="{ 'max-width': maxWidth }">
      <div
        ref="previewScaled"
        class="page-preview__scaled"
        tabindex="0"
        data-highlight="builder-preview"
        @keydown="handleKeyDown"
      >
        <ThemeProvider class="page">
          <template v-if="headerElements.length !== 0">
            <header
              class="page__header"
              :class="{
                'page__header--element-selected':
                  pageSectionWithSelectedElement === 'header',
              }"
            >
              <ElementPreview
                v-for="(element, index) in headerElements"
                :key="element.id"
                :element="element"
                :is-first-element="index === 0"
                :is-copying="copyingElementIndex === index"
                :application-context-additions="{
                  recordIndexPath: [],
                  page: currentPage,
                }"
                :show-element-id="showElementId"
                @move="moveElement($event)"
              />
            </header>
            <div class="page-preview__separator">
              <span class="page-preview__separator-label">
                {{ $t('pagePreview.header') }}
              </span>
            </div>
          </template>
          <template v-if="elements.length === 0">
            <CallToAction
              class="page-preview__empty"
              icon="baserow-icon-plus"
              icon-color="neutral"
              icon-size="large"
              icon-rounded
              @click="$refs.addElementModal.show()"
            >
              {{ $t('pagePreview.emptyMessage') }}
            </CallToAction>
          </template>
          <template v-else>
            <div
              class="page__content"
              :class="{
                'page__content--element-selected':
                  pageSectionWithSelectedElement === 'content',
              }"
            >
              <ElementPreview
                v-for="(element, index) in elements"
                :key="element.id"
                :element="element"
                :is-first-element="index === 0 && headerElements.length === 0"
                :is-copying="copyingElementIndex === index"
                :application-context-additions="{
                  recordIndexPath: [],
                  page: currentPage,
                }"
                :show-element-id="showElementId"
                @move="moveElement($event)"
              />
            </div>
          </template>
          <template v-if="footerElements.length !== 0">
            <div class="page-preview__separator">
              <span class="page-preview__separator-label">
                {{ $t('pagePreview.footer') }}
              </span>
            </div>
            <footer
              class="page__footer"
              :class="{
                'page__footer--element-selected':
                  pageSectionWithSelectedElement === 'footer',
              }"
            >
              <ElementPreview
                v-for="(element, index) in footerElements"
                :key="element.id"
                :element="element"
                :is-first-element="
                  index === 0 &&
                  headerElements.length === 0 &&
                  elements.length === 0
                "
                :is-copying="copyingElementIndex === index"
                :application-context-additions="{
                  recordIndexPath: [],
                  page: currentPage,
                }"
                :show-element-id="showElementId"
                @move="moveElement($event)"
              />
            </footer>
          </template>

          <client-only>
            <component
              :is="decorator.component"
              v-for="(decorator, index) in builderPageDecorators"
              :key="index"
              :props="decorator.props"
              show-paid-features-modal
            />
          </client-only>
        </ThemeProvider>
      </div>
      <AddElementModal ref="addElementModal" :page="currentPage" />
    </div>
  </div>
</template>

<script>
import { mapActions, mapGetters } from 'vuex'

import ElementPreview from '@baserow/modules/builder/components/elements/ElementPreview'
import { notifyIf } from '@baserow/modules/core/utils/error'
import PreviewNavigationBar from '@baserow/modules/builder/components/page/PreviewNavigationBar'
import { DIRECTIONS, PAGE_PLACES } from '@baserow/modules/builder/enums'
import AddElementModal from '@baserow/modules/builder/components/elements/AddElementModal.vue'
import ThemeProvider from '@baserow/modules/builder/components/theme/ThemeProvider.vue'
import BuilderToasts from '@baserow/modules/builder/components/BuilderToasts'

export default {
  name: 'PagePreview',
  components: {
    ThemeProvider,
    AddElementModal,
    ElementPreview,
    PreviewNavigationBar,
    BuilderToasts,
  },
  inject: ['builder', 'currentPage', 'workspace'],
  provide() {
    return { pageTopData: this.pageTop }
  },
  data() {
    return {
      // The element that is currently being copied
      copyingElementIndex: null,

      // The resize observer to resize the preview when the wrapper size change
      resizeObserver: null,

      showElementId: false,
      // Used as reactive provided pageTop value for ElementPreview
      pageTop: { value: 140 },
    }
  },
  computed: {
    DIRECTIONS: () => DIRECTIONS,
    ...mapGetters({
      deviceTypeSelected: 'page/getDeviceTypeSelected',
      getElementSelected: 'element/getSelected',
      getChildren: 'element/getChildren',
      getClosestSiblingElement: 'element/getClosestSiblingElement',
    }),
    elementSelected() {
      return this.getElementSelected(this.builder)
    },
    builderPageDecorators() {
      // Get available page decorators from registry
      return Object.values(this.$registry.getAll('builderPageDecorator') || {})
        .filter((decorator) => decorator.isDecorationAllowed(this.workspace))
        .map((decorator) => ({
          component: decorator.component,
          props: decorator.getProps(),
        }))
    },
    contextAdditions() {
      return {
        recordIndexPath: [],
      }
    },
    elements() {
      return this.$store.getters['element/getRootElements'](this.currentPage)
    },
    sharedPage() {
      return this.$store.getters['page/getSharedPage'](this.builder)
    },
    sharedElements() {
      return this.$store.getters['element/getRootElements'](this.sharedPage)
    },
    headerElements() {
      return this.sharedElements.filter(
        (element) =>
          this.$registry.get('element', element.type).getPagePlace() ===
          PAGE_PLACES.HEADER
      )
    },
    footerElements() {
      return this.sharedElements.filter(
        (element) =>
          this.$registry.get('element', element.type).getPagePlace() ===
          PAGE_PLACES.FOOTER
      )
    },
    elementSelectedId() {
      return this.elementSelected?.id
    },
    elementSelectedType() {
      if (!this.elementSelected) {
        return null
      }
      return this.$registry.get('element', this.elementSelected.type)
    },
    pageSectionWithSelectedElement() {
      if (!this.elementSelected) {
        return null
      }
      if (this.elementSelected.page_id === this.currentPage.id) {
        return PAGE_PLACES.CONTENT
      }
      const ancestorWithPagePlace = this.$store.getters['element/getAncestors'](
        this.elementSelectedPage,
        this.elementSelected,
        {
          includeSelf: true,
          predicate: (parentElement) => {
            return (
              this.$registry
                .get('element', parentElement.type)
                .getPagePlace() !== PAGE_PLACES.CONTENT
            )
          },
        }
      )[0]

      return this.$registry
        .get('element', ancestorWithPagePlace.type)
        .getPagePlace()
    },
    elementsAround() {
      if (!this.elementSelected) {
        return null
      }
      return this.elementSelectedType.getElementsAround({
        builder: this.builder,
        page: this.currentPage,
        element: this.elementSelected,
        withSharedPage: true,
      })
    },
    elementSelectedPage() {
      if (this.elementSelected) {
        // We use the page from the element itself
        return this.$store.getters['page/getById'](
          this.builder,
          this.elementSelected.page_id
        )
      }
      return null
    },
    deviceType() {
      return this.deviceTypeSelected
        ? this.$registry.get('device', this.deviceTypeSelected)
        : null
    },
    maxWidth() {
      return this.deviceType?.maxWidth
        ? `${this.deviceType.maxWidth}px`
        : 'unset'
    },
    parentOfElementSelected() {
      if (!this.elementSelected?.parent_element_id) {
        return null
      }
      return this.$store.getters['element/getElementById'](
        this.elementSelectedPage,
        this.elementSelected.parent_element_id
      )
    },
    canCreateElement() {
      return this.$hasPermission(
        'builder.page.create_element',
        this.currentPage,
        this.workspace.id
      )
    },
    canUpdateSelectedElement() {
      return this.$hasPermission(
        'builder.page.element.update',
        this.elementSelected,
        this.workspace.id
      )
    },
    canDeleteSelectedElement() {
      return this.$hasPermission(
        'builder.page.element.delete',
        this.elementSelected,
        this.workspace.id
      )
    },
  },
  watch: {
    deviceType(value) {
      this.$nextTick(() => {
        this.updatePreviewScale(value)
      })
    },
    elementSelectedId(newValue) {
      if (newValue) {
        this.$refs.previewScaled.focus()
      }
    },
  },
  mounted() {
    this.resizeObserver = new ResizeObserver(() => {
      this.onWindowResized()
    })
    this.resizeObserver.observe(this.$el)
    this.onWindowResized()
  },
  beforeDestroy() {
    this.resizeObserver.disconnect()
    document.removeEventListener('keydown', this.preventScrollIfFocused)
  },
  methods: {
    ...mapActions({
      actionDuplicateElement: 'element/duplicate',
      actionDeleteElement: 'element/delete',
      actionSelectElement: 'element/select',
      actionMoveElement: 'element/move',
    }),
    preventScrollIfFocused(e) {
      if (this.$refs.previewScaled === document.activeElement) {
        switch (e.key) {
          case 'ArrowLeft':
          case 'ArrowRight':
          case 'ArrowUp':
          case 'ArrowDown':
            e.preventDefault()
            break
        }
      }
    },
    onWindowResized() {
      this.$nextTick(() => {
        this.updatePreviewScale(this.deviceType)
      })
    },
    updatePreviewScale(deviceType) {
      // The widths are the minimum width the preview must have. If the preview dom
      // element becomes smaller than the target, it will be scaled down so that the
      // actual width remains the same, and it will preview the correct device.

      const { clientWidth: currentWidth, clientHeight: currentHeight } =
        this.$refs.preview

      const targetWidth = deviceType?.minWidth
      let scale = 1

      if (currentWidth < targetWidth) {
        // Round scale at 2 decimals
        scale = Math.round((currentWidth / targetWidth) * 100) / 100
      }

      const previewScaled = this.$refs.previewScaled
      previewScaled.style.transform = `scale(${scale})`
      previewScaled.style.transformOrigin = `0 0`
      previewScaled.style.width = `${currentWidth / scale}px`
      previewScaled.style.height = `${currentHeight / scale}px`

      // Also update page top
      this.pageTop.value =
        this.$refs.preview.getBoundingClientRect().top + 30 * scale
    },
    async moveElement({ element, direction }) {
      if (
        !this.$hasPermission(
          'builder.page.element.update',
          element,
          this.workspace.id
        )
      ) {
        return
      }

      const elementPage = this.$store.getters['page/getById'](
        this.builder,
        element.page_id
      )

      const elementType = this.$registry.get('element', element.type)

      const nextPlaces = elementType.getNextPlaces({
        builder: this.builder,
        page: this.currentPage,
        element,
      })
      if (nextPlaces[direction]) {
        try {
          await this.actionMoveElement({
            builder: this.builder,
            page: elementPage,
            elementId: element.id,
            ...nextPlaces[direction],
          })
        } catch (error) {
          notifyIf(error)
        }
      }
    },
    async moveSelectedElement(direction) {
      if (!this.elementSelected?.id || !this.canUpdateSelectedElement) {
        return
      }
      await this.moveElement({
        element: this.elementSelected,
        direction,
      })
    },
    async moveSelection(direction) {
      if (!this.elementSelected?.id) {
        return
      }
      const nextElement = this.elementsAround[direction]
      if (nextElement) {
        await this.actionSelectElement({
          builder: this.builder,
          element: nextElement,
        })
      }
    },
    async duplicateElement() {
      if (!this.elementSelected?.id || !this.canCreateElement) {
        return
      }

      this.isDuplicating = true
      try {
        await this.actionDuplicateElement({
          builder: this.builder,
          page: this.elementSelectedPage,
          elementId: this.elementSelected.id,
        })
      } catch (error) {
        notifyIf(error)
      }
      this.isDuplicating = false
    },
    async deleteElement() {
      if (!this.elementSelected?.id || !this.canDeleteSelectedElement) {
        return
      }
      try {
        const siblingElementToSelect =
          this.elementsAround[DIRECTIONS.AFTER] ||
          this.elementsAround[DIRECTIONS.BEFORE] ||
          this.elementsAround[DIRECTIONS.LEFT] ||
          this.elementsAround[DIRECTIONS.RIGHT] ||
          this.parentOfElementSelected

        await this.actionDeleteElement({
          builder: this.builder,
          page: this.elementSelectedPage,
          elementId: this.elementSelected.id,
        })
        if (siblingElementToSelect?.id) {
          await this.actionSelectElement({
            builder: this.builder,
            element: siblingElementToSelect,
          })
        }
      } catch (error) {
        notifyIf(error)
      }
    },
    selectParentElement() {
      if (this.parentOfElementSelected) {
        this.actionSelectElement({
          builder: this.builder,
          element: this.parentOfElementSelected,
        })
      }
    },
    selectChildElement() {
      const children = this.getChildren(
        this.elementSelectedPage,
        this.elementSelected
      )
      if (children.length) {
        this.actionSelectElement({
          builder: this.builder,
          element: children[0],
        })
      }
    },
    handleKeyDown(e) {
      let shouldPrevent = true
      const alternateAction = e.altKey || e.ctrlKey || e.metaKey
      switch (e.key) {
        case 'ArrowUp':
          if (alternateAction) {
            this.moveSelectedElement(DIRECTIONS.BEFORE)
          } else {
            this.moveSelection(DIRECTIONS.BEFORE)
          }
          break
        case 'ArrowDown':
          if (alternateAction) {
            this.moveSelectedElement(DIRECTIONS.AFTER)
          } else {
            this.moveSelection(DIRECTIONS.AFTER)
          }
          break
        case 'ArrowLeft':
          if (alternateAction) {
            this.moveSelectedElement(DIRECTIONS.LEFT)
          } else {
            this.moveSelection(DIRECTIONS.LEFT)
          }
          break
        case 'ArrowRight':
          if (alternateAction) {
            this.moveSelectedElement(DIRECTIONS.RIGHT)
          } else {
            this.moveSelection(DIRECTIONS.RIGHT)
          }
          break
        case 'Backspace':
        case 'Clear':
        case 'Delete':
          this.deleteElement()
          break
        case 'c':
          this.selectChildElement()
          break
        case 'd':
          this.duplicateElement()
          break
        case 'p':
          this.selectParentElement()
          break
        case 'E':
          if (alternateAction && e.shiftKey) {
            this.showElementId = !this.showElementId
          }
          break
        default:
          shouldPrevent = false
      }
      if (shouldPrevent) {
        e.stopPropagation()
        e.preventDefault()
      }
    },
  },
}
</script>
