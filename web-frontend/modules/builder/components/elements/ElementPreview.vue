<template>
  <div
    :key="element.id"
    class="element-preview"
    :class="{
      'element-preview--active': isSelected,
      'element-preview--parent-of-selected': isParentOfSelectedElement,
      'element-preview--in-error': !!errorMessage,
      'element-preview--on-top': isSelected && isAboveThreshold,
      'element-preview--not-visible':
        !isVisible && !isSelected && !isParentOfSelectedElement,
    }"
    @click="onSelect"
  >
    <div v-if="isSelected" class="element-preview__tags">
      <div class="element-preview__name-tag">
        {{ elementType.name }}
        <i v-if="!isVisible" class="iconoir-eye-off" />
      </div>
      <div v-if="errorMessage" class="element-preview__error-tag">
        {{ errorMessage }}
      </div>
    </div>
    <InsertElementButton
      v-show="isSelected"
      v-if="canCreate"
      class="element-preview__insert element-preview__insert--top"
      @click="showAddElementModal(DIRECTIONS.BEFORE)"
    />
    <ElementMenu
      v-if="isSelected && canUpdate"
      :directions="directions"
      :allowed-directions="allowedMoveDirections"
      :is-duplicating="isDuplicating"
      :has-parent="!!parentElement"
      @delete="deleteElement"
      @move="onMove"
      @duplicate="duplicateElement"
      @select-parent="selectParentElement()"
    />
    <PageElement
      :element="element"
      :mode="mode"
      class="element--read-only"
      :show-element-id="showElementId"
      @move="$emit('move', $event)"
    />

    <InsertElementButton
      v-show="isSelected"
      v-if="canCreate"
      class="element-preview__insert element-preview__insert--bottom"
      @click="showAddElementModal(DIRECTIONS.AFTER)"
    />
    <AddElementModal
      v-if="canCreate"
      ref="addElementModal"
      :page="elementPage"
    />
  </div>
</template>

<script>
import ElementMenu from '@baserow/modules/builder/components/elements/ElementMenu'
import InsertElementButton from '@baserow/modules/builder/components/elements/InsertElementButton'
import PageElement from '@baserow/modules/builder/components/page/PageElement'
import { DIRECTIONS } from '@baserow/modules/builder/enums'
import AddElementModal from '@baserow/modules/builder/components/elements/AddElementModal'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { mapActions, mapGetters } from 'vuex'
import { checkIntermediateElements } from '@baserow/modules/core/utils/dom'
import applicationContextMixin from '@baserow/modules/builder/mixins/applicationContext'

export default {
  name: 'ElementPreview',
  components: {
    AddElementModal,
    ElementMenu,
    InsertElementButton,
    PageElement,
  },
  mixins: [applicationContextMixin],
  inject: ['workspace', 'builder', 'mode', 'currentPage', 'pageTopData'],
  props: {
    element: {
      type: Object,
      required: true,
    },
    isFirstElement: {
      type: Boolean,
      required: false,
      default: false,
    },
    showElementId: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      isDuplicating: false,
      isAboveThreshold: false,
      observer: null,
    }
  },
  computed: {
    ...mapGetters({
      getElementSelected: 'element/getSelected',
      elementAncestors: 'element/getAncestors',
      getClosestSiblingElement: 'element/getClosestSiblingElement',
      loggedUser: 'userSourceUser/getUser',
    }),
    applicationContext() {
      return {
        ...this.injectedApplicationContext,
        ...this.applicationContextAdditions,
        element: this.element,
      }
    },
    pageTop() {
      return this.pageTopData.value
    },
    elementSelected() {
      return this.getElementSelected(this.builder)
    },
    elementPage() {
      // We use the page from the element itself
      return this.$store.getters['page/getById'](
        this.builder,
        this.element.page_id
      )
    },
    isVisible() {
      return this.elementType.isVisible({
        element: this.element,
        applicationContext: this.applicationContext,
      })
    },
    DIRECTIONS: () => DIRECTIONS,
    directions() {
      return [
        DIRECTIONS.BEFORE,
        DIRECTIONS.AFTER,
        DIRECTIONS.LEFT,
        DIRECTIONS.RIGHT,
      ]
    },
    parentOfElementSelected() {
      if (!this.elementSelected?.parent_element_id) {
        return null
      }
      return this.$store.getters['element/getElementById'](
        this.elementPage,
        this.elementSelected.parent_element_id
      )
    },
    elementsAround() {
      return this.elementType.getElementsAround({
        builder: this.builder,
        page: this.currentPage,
        withSharedPage: true,
        element: this.element,
      })
    },
    nextPlaces() {
      return this.elementType.getNextPlaces({
        builder: this.builder,
        page: this.elementPage,
        element: this.element,
      })
    },
    allowedMoveDirections() {
      return Object.entries(this.nextPlaces)
        .filter(([, nextPlace]) => !!nextPlace)
        .map(([direction]) => direction)
    },
    canCreate() {
      return this.$hasPermission(
        'builder.page.create_element',
        this.currentPage,
        this.workspace.id
      )
    },
    canUpdate() {
      return this.$hasPermission(
        'builder.page.element.update',
        this.element,
        this.workspace.id
      )
    },
    isSelected() {
      return this.element.id === this.elementSelected?.id
    },
    selectedElementAncestorIds() {
      if (!this.elementSelected) {
        return []
      }
      return this.elementAncestors(this.elementPage, this.elementSelected).map(
        ({ id }) => id
      )
    },
    isParentOfSelectedElement() {
      return this.selectedElementAncestorIds.includes(this.element.id)
    },
    elementType() {
      return this.$registry.get('element', this.element.type)
    },
    parentElement() {
      if (!this.element.parent_element_id) {
        return null
      }
      return this.$store.getters['element/getElementById'](
        this.elementPage,
        this.element.parent_element_id
      )
    },
    errorMessage() {
      return this.elementType.getErrorMessage(
        this.element,
        this.applicationContext
      )
    },
  },
  watch: {
    /**
     * If the element is currently selected, i.e. in the Elements Context menu,
     * ensure the element is scrolled into the viewport.
     */
    isSelected(newValue, old) {
      if (newValue && !old) {
        const rect = this.$el.getBoundingClientRect()
        const isTopVisible =
          rect.top >= 0 &&
          rect.top <=
            (window.innerHeight || document.documentElement.clientHeight)

        if (!isTopVisible) {
          this.$el.scrollIntoView({ behavior: 'smooth', block: 'start' })
        }
      }
    },
    pageTop() {
      this.setupIntersectionObserver()
    },
    /**
     * If the currently selected element in the Page Preview has moved, ensure
     * the element is scrolled into the viewport.
     */
    element: {
      handler(newValue, old) {
        if (
          (newValue.place_in_container !== old.place_in_container ||
            newValue.order !== old.order) &&
          this.isSelected
        ) {
          this.$el.scrollIntoView({ behavior: 'smooth', block: 'center' })
        }
      },
      deep: true,
    },
  },
  mounted() {
    if (this.isFirstElement) {
      this.actionSelectElement({ builder: this.builder, element: this.element })
    }
    this.setupIntersectionObserver()
  },
  beforeDestroy() {
    if (this.observer) {
      this.observer.disconnect()
    }
  },
  methods: {
    ...mapActions({
      actionDuplicateElement: 'element/duplicate',
      actionDeleteElement: 'element/delete',
      actionSelectElement: 'element/select',
    }),
    setupIntersectionObserver() {
      if (this.observer) {
        this.observer.disconnect()
      }

      // Ensure pageTop is a valid number to prevent IntersectionObserver error
      const topMargin =
        typeof this.pageTop === 'number' && !isNaN(this.pageTop)
          ? this.pageTop
          : 0

      const options = {
        root: null,
        rootMargin: `-${topMargin}px 0px 0px 0px`,
        threshold: [0, 1],
      }

      this.observer = new IntersectionObserver((entries) => {
        const rect = entries[0].boundingClientRect
        this.isAboveThreshold = rect.top < topMargin
      }, options)

      this.$nextTick(() => {
        this.observer.observe(this.$el)
      })
    },
    onMove(direction) {
      this.$emit('move', { element: this.element, direction })
    },
    onSelect($event) {
      // Here we check that the event has been emitted for this particular element
      // If we found an intermediate DOM element with the class `element-preview`,
      // or `element-preview__menu`, then we don't select the element.
      // It means it hasn't been originated by this element, so we don't select it.
      if (
        !checkIntermediateElements(this.$el, $event.target, (el) => {
          return (
            el.classList.contains('element-preview') ||
            el.classList.contains('element-preview__menu')
          )
        })
      ) {
        this.actionSelectElement({
          builder: this.builder,
          element: this.element,
        })
      }
    },
    showAddElementModal(direction) {
      const rootElement = this.$store.getters['element/getAncestors'](
        this.elementPage,
        this.element,
        { includeSelf: true }
      )[0]
      const rootElementType = this.$registry.get('element', rootElement.type)
      const pagePlace = rootElementType.getPagePlace()

      this.$refs.addElementModal.show({
        placeInContainer: this.element.place_in_container,
        parentElementId: this.element.parent_element_id,
        beforeId: this.getBeforeId(direction),
        pagePlace,
      })
    },
    getBeforeId(direction) {
      return direction === DIRECTIONS.BEFORE
        ? this.element.id
        : this.elementsAround[DIRECTIONS.AFTER]?.id || null
    },
    async duplicateElement() {
      this.isDuplicating = true
      try {
        await this.actionDuplicateElement({
          builder: this.builder,
          page: this.elementPage,
          elementId: this.element.id,
        })
      } catch (error) {
        notifyIf(error)
      }
      this.isDuplicating = false
    },
    async deleteElement() {
      try {
        const siblingElementToSelect =
          this.elementsAround[DIRECTIONS.AFTER] ||
          this.elementsAround[DIRECTIONS.BEFORE] ||
          this.elementsAround[DIRECTIONS.LEFT] ||
          this.elementsAround[DIRECTIONS.RIGHT] ||
          this.parentOfElementSelected

        await this.actionDeleteElement({
          builder: this.builder,
          page: this.elementPage,
          elementId: this.element.id,
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
  },
}
</script>
