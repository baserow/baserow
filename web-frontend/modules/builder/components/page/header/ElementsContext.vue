<template>
  <Context
    class="select elements-context"
    max-height-if-outside-viewport
    @shown="shown()"
  >
    <div class="select__search">
      <i class="select__search-icon iconoir-search"></i>
      <input
        ref="search"
        v-model="search"
        type="text"
        class="elements-context__search-input"
        :placeholder="$t('elementsContext.searchPlaceholder')"
      />
    </div>
    <div class="elements-context__elements">
      <ElementsList
        v-if="headerElementsVisible"
        :elements="headerElements"
        :filtered-search-elements="filteredHeaderElements"
        @select="selectElement($event)"
      />
      <ElementsList
        v-if="contentElementsVisible"
        :elements="rootElements"
        :filtered-search-elements="filteredContentElements"
        @select="selectElement($event)"
      />
      <div
        v-if="!contentElementsVisible && !isSearching"
        class="elements-list elements-list--empty"
      >
        {{ $t('elementsContext.noPageElements') }}
      </div>
      <ElementsList
        v-if="footerElementsVisible"
        :elements="footerElements"
        :filtered-search-elements="filteredFooterElements"
        @select="selectElement($event)"
      />
      <div
        v-if="!elementsVisible && isSearching"
        class="elements-list elements-list--empty"
      >
        {{ $t('elementsContext.noElements') }}
      </div>
    </div>
    <div
      v-if="
        $hasPermission('builder.page.create_element', currentPage, workspace.id)
      "
      class="elements-context__footer"
    >
      <div class="elements-context__footer-create">
        <AddElementButton
          :class="{
            'margin-top-1': !elementsVisible,
          }"
          @click="$refs.addElementModal.show()"
        />
      </div>
    </div>
    <AddElementModal
      v-if="
        $hasPermission('builder.page.create_element', currentPage, workspace.id)
      "
      ref="addElementModal"
      :page="currentPage"
      @element-added="onElementAdded"
    />
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'
import ElementsList from '@baserow/modules/builder/components/elements/ElementsList'
import AddElementButton from '@baserow/modules/builder/components/elements/AddElementButton'
import AddElementModal from '@baserow/modules/builder/components/elements/AddElementModal'
import { mapActions } from 'vuex'
import { isSubstringOfStrings } from '@baserow/modules/core/utils/string'
import { PAGE_PLACES } from '@baserow/modules/builder/enums'

export default {
  name: 'ElementsContext',
  components: { AddElementModal, AddElementButton, ElementsList },
  mixins: [context],
  inject: ['workspace', 'currentPage', 'builder', 'mode'],
  data() {
    return {
      search: null,
    }
  },
  computed: {
    isSearching() {
      return Boolean(this.search)
    },
    elementsVisible() {
      return (
        (this.search &&
          (this.filteredContentElements.length ||
            this.filteredHeaderElements.length ||
            this.filteredFooterElements.length)) ||
        (!this.search &&
          (this.rootElements.length ||
            this.headerElements.length ||
            this.footerElements.length))
      )
    },
    contentElementsVisible() {
      return (
        (this.search && this.filteredContentElements.length) ||
        (!this.search && this.rootElements.length)
      )
    },
    headerElementsVisible() {
      return (
        (this.search && this.filteredHeaderElements.length) ||
        (!this.search && this.headerElements.length)
      )
    },
    footerElementsVisible() {
      return (
        (this.search && this.filteredFooterElements.length) ||
        (!this.search && this.footerElements.length)
      )
    },
    rootElements() {
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
    filteredContentElements() {
      return this.filterElements(this.rootElements, this.currentPage)
    },
    filteredHeaderElements() {
      return this.filterElements(this.headerElements, this.sharedPage)
    },
    filteredFooterElements() {
      return this.filterElements(this.footerElements, this.sharedPage)
    },
  },
  methods: {
    ...mapActions({
      actionSelectElement: 'element/select',
    }),
    /*
     * Given an element, this method will return the corpus we want to
     * search against when a user enters a search query. Should we want
     * to search both the 'display name' and the element type name, this
     * method can be easily adapted to combine the two and return it.
     */
    getElementCorpus(element, page) {
      const elementType = this.$registry.get('element', element.type)
      return elementType.getDisplayName(element, {
        builder: this.builder,
        page,
        mode: this.mode,
        element,
      })
    },
    onElementAdded() {
      this.hide()
    },
    selectElement(element) {
      this.actionSelectElement({ builder: this.builder, element })
      this.hide()
    },
    /*
     * When a user searches for elements in the list, this computed method
     * is responsible for finding *all* matching elements, and then finding
     * each ancestor of those elements. This ensures that we only display
     * elements in tree until our matching element is found. For example, a
     * tree such as the following:
     *
     * - Repeat
     *     - Column
     *         - Heading 1
     *         - Repeat
     *             - Image
     *         - Heading 2
     *
     * With a search query of "heading" would result in:
     *
     * - Repeat
     *     - Column
     *         - Heading 1
     *         - Heading 2
     *
     * With a search query of "image" would result in:
     *
     * - Repeat
     *     - Column
     *         - Repeat
     *             - Image
     */
    filterElements(elements, page) {
      let filteredToElementIds = []
      if (!this.search) {
        // If there's no search query, then there are no
        // elements to narrow the results down to.
        return filteredToElementIds
      }

      // Iterate over all the root-level elements.
      elements.forEach((element) => {
        // Find this element's descendants and loop over them.
        const descendants = this.$store.getters['element/getDescendants'](
          page,
          element
        )
        descendants.forEach((descendant) => {
          // Build this descendant's corpus (for now, display name only)
          // and check if it matches the search query.
          const descendantCorpus = this.getElementCorpus(descendant, page)
          if (isSubstringOfStrings([descendantCorpus], this.search)) {
            // The descendant matches. We need to include *this* element,
            // and all its *ancestors* in our list of narrowed results.
            const ascendants = this.$store.getters['element/getAncestors'](
              page,
              descendant
            )
            filteredToElementIds.push(descendant.id)
            filteredToElementIds = filteredToElementIds.concat(
              ascendants.map((a) => a.id)
            )
          }
        })

        // Test of the root element itself matches the search query.
        // if it does, it gets included in the narrowed results too.
        const rootCorpus = this.getElementCorpus(element, page)
        if (isSubstringOfStrings([rootCorpus], this.search)) {
          // The root element matches.
          filteredToElementIds.push(element.id)
        }
      })
      filteredToElementIds = [...new Set(filteredToElementIds)]
      return filteredToElementIds
    },
    shown() {
      this.search = null
      this.$nextTick(() => {
        this.$refs.search.focus()
      })
    },
  },
}
</script>
