<template>
  <Modal>
    <h2 class="box__title">{{ $t('addElementModal.title') }}</h2>
    <FormInput
      v-model="search"
      size="large"
      class="margin-bottom-2"
      :placeholder="$t('addElementModal.searchPlaceholder')"
      icon-right="iconoir-search"
    />
    <div class="add-element-modal__element-cards">
      <AddElementCard
        v-for="elementType in elementTypes"
        :key="elementType.getType()"
        :element-type="elementType"
        :loading="addingElementType === elementType.getType()"
        :disabled="isElementTypeDisabled(elementType)"
        :disabled-message="getElementTypeDisabledMessage(elementType)"
        @click="addElement(elementType)"
      />
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import AddElementCard from '@baserow/modules/builder/components/elements/AddElementCard'
import { isSubstringOfStrings } from '@baserow/modules/core/utils/string'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { mapActions } from 'vuex'
import { PAGE_PLACES } from '../../enums'

export default {
  name: 'AddElementModal',
  components: { AddElementCard },
  mixins: [modal],
  inject: ['builder', 'currentPage'],
  props: {
    page: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      search: '',
      placeInContainer: null,
      beforeId: null,
      parentElementId: null,
      pagePlace: null,
      addingElementType: null,
    }
  },
  computed: {
    elementTypes() {
      const elementTypesAll = Object.values(this.$registry.getAll('element'))
      return elementTypesAll.filter((elementType) =>
        isSubstringOfStrings(
          [elementType.name, elementType.description],
          this.search
        )
      )
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
  },
  methods: {
    getElementTypeDisabledMessage(elementType) {
      if (elementType.getType() === this.addingElementType) {
        // This type is disabled while we add it.
        return this.$t('addElementModal.elementInProgress')
      }

      return elementType.isDisallowedReason({
        builder: this.builder,
        page: this.page,
        placeInContainer: this.placeInContainer,
        parentElement: this.parentElement,
        beforeElement: this.beforeElement,
        pagePlace: this.pagePlace,
      })
    },
    isElementTypeDisabled(elementType) {
      return !!this.getElementTypeDisabledMessage(elementType)
    },
    ...mapActions({
      actionCreateElement: 'element/create',
    }),

    show(
      { placeInContainer, beforeId, parentElementId, pagePlace } = {},
      ...args
    ) {
      this.placeInContainer = placeInContainer
      this.beforeId = beforeId
      this.parentElementId = parentElementId
      this.pagePlace = pagePlace
      modal.methods.show.bind(this)(...args)
    },

    async addElement(elementType) {
      if (this.isElementTypeDisabled(elementType)) {
        return false
      }
      this.addingElementType = elementType.getType()

      let beforeId = this.beforeId
      let destinationPage

      if (this.parentElementId) {
        // The page must be the same as the parent one
        destinationPage =
          this.parentElement.page_id === this.currentPage.id
            ? this.currentPage
            : this.sharedPage
      } else {
        // The page is forced by the element type page place
        destinationPage =
          elementType.getPagePlace() === PAGE_PLACES.CONTENT
            ? this.currentPage
            : this.sharedPage
        // If the before element doesn't belong to the same page we must ignore it
        if (
          this.beforeElement &&
          this.beforeElement.page_id !== destinationPage.id
        ) {
          beforeId = null
        }
      }

      try {
        await this.actionCreateElement({
          page: destinationPage,
          elementType: elementType.getType(),
          beforeId,
          values: {
            parent_element_id: this.parentElementId,
            place_in_container: this.placeInContainer,
          },
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
