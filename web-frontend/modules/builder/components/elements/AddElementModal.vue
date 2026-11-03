<template>
  <ItemPickerModal
    ref="modal"
    :title="$t('addElementModal.title')"
    :search-placeholder="$t('addElementModal.searchPlaceholder')"
    :groups="elementGroups"
    @show="isOpen = true"
    @hidden="isOpen = false"
  >
    <template #items="{ items }">
      <AddElementCard
        v-for="elementType in items"
        :key="elementType.getType()"
        :element-type="elementType"
        :loading="addingElementType === elementType.getType()"
        :workspace="workspace"
        :builder="builder"
        :page="page"
        :place-in-container="placeInContainer"
        :parent-element="parentElement"
        :before-element="beforeElement"
        :after-element="afterElement"
        :page-place="pagePlace"
        @click="addElement(elementType)"
      />
    </template>
  </ItemPickerModal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import AddElementCard from '@baserow/modules/builder/components/elements/AddElementCard'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { mapActions } from 'vuex'
import { PAGE_PLACES } from '@baserow/modules/builder/enums'
import ItemPickerModal from '@baserow/modules/core/components/ItemPickerModal'

export default {
  name: 'AddElementModal',
  components: { AddElementCard, ItemPickerModal },
  mixins: [modal],
  inject: ['workspace', 'builder', 'currentPage'],
  props: {
    page: {
      type: Object,
      required: true,
    },
  },
  emits: ['element-added'],
  data() {
    return {
      isOpen: false,
      placeInContainer: null,
      beforeId: null,
      afterId: null,
      parentElementId: null,
      pagePlace: null,
      addingElementType: null,
    }
  },
  computed: {
    elementGroups() {
      if (!this.isOpen) {
        return []
      }

      const elementTypes = Object.values(this.$registry.getAll('element'))
      return ['baseElement', 'layoutElement', 'formElement'].map((id) => {
        const items = elementTypes.filter(
          (elementType) => (elementType.category() || 'baseElement') === id
        )
        return {
          id,
          label: this.$t(`addElementCategory.${id}`),
          items,
          initiallyCollapsed: items.every((elementType) =>
            elementType.isDisallowedReason({
              workspace: this.workspace,
              builder: this.builder,
              page: this.page,
              placeInContainer: this.placeInContainer,
              parentElement: this.parentElement,
              beforeElement: this.beforeElement,
              afterElement: this.afterElement,
              pagePlace: this.pagePlace,
            })
          ),
        }
      })
    },
    sharedPage() {
      return this.$store.getters['page/getSharedPage'](this.builder)
    },
    parentElement() {
      if (this.parentElementId) {
        return this.$store.getters['element/getElementByIdInPages'](
          [this.currentPage, this.sharedPage],
          this.parentElementId
        )
      }
      return null
    },
    beforeElement() {
      if (this.beforeId) {
        return this.$store.getters['element/getElementByIdInPages'](
          [this.currentPage, this.sharedPage],
          this.beforeId
        )
      }
      return null
    },
    afterElement() {
      if (this.afterId) {
        return this.$store.getters['element/getElementByIdInPages'](
          [this.currentPage, this.sharedPage],
          this.afterId
        )
      }
      return null
    },
  },
  methods: {
    ...mapActions({
      actionCreateElement: 'element/create',
    }),

    show(
      { placeInContainer, beforeId, afterId, parentElementId, pagePlace } = {},
      ...args
    ) {
      this.placeInContainer = placeInContainer
      this.beforeId = beforeId
      this.afterId = afterId || null
      this.parentElementId = parentElementId
      this.pagePlace = pagePlace
      modal.methods.show.bind(this)(...args)
    },

    async addElement(elementType) {
      this.addingElementType = elementType.getType()

      let destinationPage
      let referenceElementId = null
      let position = 'south'
      let placeInContainer = ''

      if (this.parentElementId) {
        // The page must be the same as the parent one.
        destinationPage =
          this.parentElement.page_id === this.currentPage.id
            ? this.currentPage
            : this.sharedPage

        if (this.beforeId) {
          // Insert before a specific element inside the container.
          referenceElementId = this.beforeId
          position = 'north'
        } else {
          // Append to the end of the container slot.
          const elementsInPlace = this.$store.getters[
            'element/getElementsInPlace'
          ](destinationPage, this.parentElementId, this.placeInContainer)

          if (elementsInPlace.length > 0) {
            referenceElementId = elementsInPlace.at(-1).id
            position = 'south'
          } else {
            referenceElementId = this.parentElementId
            position = 'child'
            placeInContainer = this.placeInContainer
          }
        }
      } else {
        // Root-level insertion.
        destinationPage =
          elementType.getPagePlace() === PAGE_PLACES.CONTENT
            ? this.currentPage
            : this.sharedPage

        let beforeId = this.beforeId
        if (
          this.beforeElement &&
          this.beforeElement.page_id !== destinationPage.id
        ) {
          beforeId = null
        }

        let afterId = this.afterId
        let afterNulledCrossPage = false
        if (
          this.afterElement &&
          this.afterElement.page_id !== destinationPage.id
        ) {
          afterId = null
          afterNulledCrossPage = true
        }

        if (beforeId) {
          referenceElementId = beforeId
          position = 'north'
        } else if (afterId) {
          referenceElementId = afterId
          position = 'south'
        } else if (
          afterNulledCrossPage &&
          this.afterElement?.page_id === this.sharedPage.id
        ) {
          // afterElement was on the shared page (e.g. a header) but the new
          // element goes to the current page (content zone). The cursor is just
          // south of the header zone, so the element should appear first in the
          // content zone — north of whatever is currently first there.
          // Note: when afterElement is on the current page and destination is the
          // shared page (e.g. adding a footer south of last content), we fall
          // through to append, which is the correct behaviour for that case.
          const firstOnDestination =
            this.$store.getters['element/getRootElements'](destinationPage)[0]
          if (firstOnDestination) {
            referenceElementId = firstOnDestination.id
            position = 'north'
          }
          // else: destination page is empty → append (referenceElementId=null,
          // position='south') is correct.
        }
        // else: referenceElementId=null, position='south' → appends to end
      }

      try {
        await this.actionCreateElement({
          builder: this.builder,
          page: destinationPage,
          elementType: elementType.getType(),
          referenceElementId,
          position,
          placeInContainer,
          values: {},
        })

        this.$emit('element-added')
        this.hide()
      } catch (error) {
        notifyIf(error)
      }
      this.addingElementType = null
    },
  },
}
</script>
