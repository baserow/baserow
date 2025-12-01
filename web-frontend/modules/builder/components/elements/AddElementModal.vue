<template>
  <Modal class="add-element-modal">
    <h2 class="box__title">{{ $t('addElementModal.title') }}</h2>
    <div class="add-element-modal__content">
      <FormInput
        ref="search"
        v-model="search"
        size="large"
        class="add-element-modal__search"
        :placeholder="$t('addElementModal.searchPlaceholder')"
        icon-left="iconoir-search"
      />
      <div class="add-element-modal__element-cards">
        <template v-for="group in elementTypes">
          <div
            v-if="group.elementTypes.length > 0"
            :key="group.subject"
            class="add-element-modal__category"
          >
            <Expandable
              :default-expanded="!initiallyCollapsedCategories[group.subject]"
            >
              <template #header="{ toggle, expanded }">
                <a class="add-element-modal__category-title" @click="toggle">
                  {{ group.label }}
                  <i
                    class="add-element-modal__category-arrow"
                    :class="{
                      'iconoir-nav-arrow-down': expanded,
                      'iconoir-nav-arrow-right': !expanded,
                    }"
                  />
                </a>
              </template>
              <template #default>
                <div class="add-element-modal__category-content">
                  <AddElementCard
                    v-for="elementType in group.elementTypes"
                    :key="elementType.getType()"
                    :element-type="elementType"
                    :loading="addingElementType === elementType.getType()"
                    :workspace="workspace"
                    :builder="builder"
                    :page="page"
                    :place-in-container="placeInContainer"
                    :parent-element="parentElement"
                    :before-element="beforeElement"
                    :page-place="pagePlace"
                    @click="addElement(elementType)"
                  />
                </div>
              </template>
            </Expandable>
          </div>
        </template>
      </div>
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import AddElementCard from '@baserow/modules/builder/components/elements/AddElementCard'
import { isSubstringOfStrings } from '@baserow/modules/core/utils/string'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { mapActions } from 'vuex'
import { PAGE_PLACES } from '@baserow/modules/builder/enums'
import Expandable from '@baserow/modules/core/components/Expandable'

export default {
  name: 'AddElementModal',
  components: { AddElementCard, Expandable },
  mixins: [modal],
  inject: ['workspace', 'builder', 'currentPage'],
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
      initiallyCollapsedCategories: {},
    }
  },
  computed: {
    elementTypes() {
      const elementTypesAll = Object.values(this.$registry.getAll('element'))
      const filteredTypes = elementTypesAll.filter((elementType) =>
        isSubstringOfStrings(
          [elementType.name, elementType.description],
          this.search
        )
      )

      // Define group categories
      const groupsList = ['baseElement', 'layoutElement', 'formElement']

      // Create group objects with label and empty elementTypes array
      const groups = groupsList.map((subject) => ({
        subject,
        label: this.$t(`addElementCategory.${subject}`),
        elementTypes: [],
      }))

      // Fill other groups with filtered element types
      filteredTypes.forEach((elementType) => {
        const category = elementType.category() || 'baseElement'

        // Add element to its standard category, even if it's already in suggested elements
        if (category !== 'suggestedElement') {
          const group = groups.find((g) => g.subject === category)
          if (group) {
            group.elementTypes.push(elementType)
          }
        }
      })

      return groups
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
    ...mapActions({
      actionCreateElement: 'element/create',
    }),

    async show(
      { placeInContainer, beforeId, parentElementId, pagePlace } = {},
      ...args
    ) {
      this.placeInContainer = placeInContainer
      this.beforeId = beforeId
      this.parentElementId = parentElementId
      this.pagePlace = pagePlace
      modal.methods.show.bind(this)(...args)

      await this.$nextTick()
      // Let's focus search input
      this.$refs.search.focus()
    },

    async addElement(elementType) {
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
          builder: this.builder,
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
