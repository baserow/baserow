<template>
  <Modal
    ref="modal"
    :content-scrollable="hasSearchTerm"
    :close-button="false"
    :box-padding="false"
    :content-padding="false"
    @show="onShow"
  >
    <template #content>
      <div
        class="workspace-search"
        :class="{
          'workspace-search--expanded': hasSearchTerm,
          'workspace-search--keyboard-nav': isKeyboardNavigating,
        }"
      >
        <div class="workspace-search__header">
          <FormInput
            ref="searchInput"
            v-model="searchTerm"
            size="large"
            icon-left="iconoir-search"
            :icon-right="searchTerm ? 'iconoir-cancel' : null"
            :placeholder="$t('workspaceSearch.searchEverything')"
            class="workspace-search__input form-input--no-border"
            @keydown="handleKeydown"
            @icon-right-click="clearSearch"
          />
        </div>

        <div
          v-if="hasSearchTerm"
          class="workspace-search__content"
          @scroll="handleScroll"
          @mousemove="onMouseMove"
        >
          <!-- Search results -->
          <div v-if="hasResults" class="workspace-search__results">
            <div class="workspace-search__results-list">
              <div
                v-for="(result, index) in allResults"
                :key="`${result.type}-${result.id}-${index}`"
                class="workspace-search__result-item"
                :class="{
                  'workspace-search__result-item--active':
                    activeIndex === index,
                }"
                @click="selectResult(result)"
                @mouseenter="handleMouseEnter(index)"
              >
                <div class="workspace-search__result-icon">
                  <i :class="getResultIcon(result.type)"></i>
                </div>
                <div class="workspace-search__result-main">
                  <div class="workspace-search__result-title">
                    {{ displayFor(result).title }}
                  </div>
                  <div
                    v-if="displayFor(result).subtitle"
                    class="workspace-search__result-subtitle"
                  >
                    {{ displayFor(result).subtitle }}
                  </div>
                  <div
                    v-if="
                      displayFor(result).descriptionSegments &&
                      displayFor(result).descriptionSegments.length
                    "
                    class="workspace-search__result-description"
                  >
                    <span
                      v-for="(seg, sIdx) in displayFor(result)
                        .descriptionSegments"
                      :key="sIdx"
                      :class="{
                        'workspace-search__result-highlight': seg.highlighted,
                      }"
                    >
                      {{ seg.text }}
                    </span>
                  </div>
                </div>
                <div
                  v-if="activeIndex === index"
                  class="workspace-search__result-enter"
                >
                  <kbd class="workspace-search__keys">
                    <img :src="enterIcon" />
                  </kbd>
                </div>
              </div>
            </div>

            <div
              v-show="hasMoreResults"
              class="infinite-scroll__loading-wrapper"
            >
              <div v-if="isLoadingMore" class="loading"></div>
            </div>
          </div>

          <!-- No results -->
          <div
            v-else-if="!loading && !isSearching"
            class="workspace-search__empty"
          >
            <div class="workspace-search__empty-icon">
              <i class="iconoir-search"></i>
            </div>
            <div class="workspace-search__empty-title">
              {{ $t('workspaceSearch.noResults') }}
            </div>
            <div class="workspace-search__empty-subtitle">
              {{ $t('workspaceSearch.noResultsSubtitle', { searchTerm }) }}
            </div>
          </div>

          <!-- Loading state -->
          <div v-else class="workspace-search__loading">
            <div class="workspace-search__loading-spinner">
              <div class="loading"></div>
            </div>
            <div class="workspace-search__loading-text">
              {{ $t('workspaceSearch.searching') }}
            </div>
          </div>
        </div>

        <!-- Bottom toolbar with keyboard shortcuts when typing -->
        <div v-if="hasSearchTerm" class="workspace-search__footer">
          <div class="workspace-search__shortcuts">
            <div class="workspace-search__shortcuts-left">
              <div class="workspace-search__shortcut">
                <kbd class="workspace-search__keys"
                  ><i class="iconoir-arrow-up"></i
                ></kbd>
                <kbd class="workspace-search__keys"
                  ><i class="iconoir-arrow-down"></i
                ></kbd>
                {{ $t('workspaceSearch.navigate') }}
              </div>
            </div>
            <div class="workspace-search__shortcuts-right">
              <div class="workspace-search__shortcut">
                <kbd>esc</kbd> {{ $t('workspaceSearch.close') }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </Modal>
</template>

<script>
import debounce from 'lodash/debounce'
import { mapGetters, mapState } from 'vuex'
import { searchTypeRegistry } from '@baserow/modules/core/search/types/registry'
import enterIcon from '@baserow/modules/core/assets/icons/enter.svg'

export default {
  name: 'WorkspaceSearchModal',

  data() {
    return {
      searchTerm: '',
      activeIndex: -1,
      hasMoreResults: false,
      isLoadingMore: false,
      isSearching: false,
      isKeyboardNavigating: false,
      currentPage: 1,
      minChars: 3,
      pageSize: 10,
      initialLoadPages: 2,
      scrollLoadPages: 3,
    }
  },

  computed: {
    ...mapState('workspaceSearch', ['loading', 'results']),
    ...mapGetters('workspaceSearch', [
      'hasResults',
      'totalResultCount',
      'getAllResults',
    ]),

    enterIcon() {
      return enterIcon
    },

    hasSearchTerm() {
      return this.searchTerm && this.searchTerm.length >= this.minChars
    },

    currentWorkspace() {
      return (
        this.selectedWorkspace ||
        this.$store.getters['workspace/get'](this.$route.params.workspaceId)
      )
    },

    selectedWorkspace() {
      return this.$store.state.workspace.selected
    },

    allResults() {
      return this.getAllResults
    },

    maxIndex() {
      return Math.max(0, this.allResults.length - 1)
    },
  },

  watch: {
    searchTerm(newValue) {
      if (newValue && newValue.length >= this.minChars) {
        this.isSearching = true
        this.currentPage = 1
        this.hasMoreResults = false
        this.isLoadingMore = false
        this.$store.dispatch('workspaceSearch/clearSearch')
      } else {
        this.isSearching = false
        this.currentPage = 1
        this.hasMoreResults = false
        this.isLoadingMore = false
        this.$store.dispatch('workspaceSearch/clearSearch')
      }
      this.debouncedSearch(newValue)
    },
    'selectedWorkspace.id'(newId, oldId) {
      if (newId !== oldId) {
        this.clearSearch()
      }
    },
  },

  mounted() {
    this.$nextTick(() => {
      this.attachScrollListener()
    })
  },

  beforeDestroy() {
    this.removeScrollListener()
  },

  methods: {
    onMouseMove(event) {
      if (event && (event.movementX !== 0 || event.movementY !== 0)) {
        this.isKeyboardNavigating = false
      }
    },
    displayFor(result) {
      return searchTypeRegistry.formatResultDisplay(result.type, result, {
        searchTerm: this.searchTerm,
      })
    },
    attachScrollListener() {
      try {
        const modalElement = this.$refs.modal?.$el

        if (modalElement && typeof modalElement.querySelector === 'function') {
          const modalContent = modalElement.querySelector('.modal__box-content')

          if (modalContent) {
            modalContent.addEventListener('scroll', this.handleScroll)
          }
        }
      } catch (error) {
        console.error('Error attaching scroll listener:', error)
      }
    },

    removeScrollListener() {
      try {
        const modalElement = this.$refs.modal?.$el
        if (modalElement && typeof modalElement.querySelector === 'function') {
          const modalContent = modalElement.querySelector('.modal__box-content')
          if (modalContent) {
            modalContent.removeEventListener('scroll', this.handleScroll)
          }
        }
      } catch (error) {
        console.error('Error removing scroll listener:', error)
      }
    },

    show() {
      this.$refs.modal.show()
    },

    hide() {
      this.$refs.modal.hide()
    },

    onShow() {
      this.$nextTick(() => {
        if (this.$refs.searchInput) {
          this.$refs.searchInput.focus()
        }
        this.attachScrollListener()
      })
    },

    clearSearch() {
      this.searchTerm = ''
      this.activeIndex = -1
      this.currentPage = 1
      this.hasMoreResults = false
      this.isLoadingMore = false
      this.isSearching = false
      this.$store.dispatch('workspaceSearch/clearSearch')
    },

    debouncedSearch: debounce(async function (searchTerm) {
      if (!searchTerm || searchTerm.length < this.minChars) {
        this.$store.dispatch('workspaceSearch/clearSearch')
        this.currentPage = 1
        this.hasMoreResults = false
        this.isSearching = false
        return
      }

      if (!this.currentWorkspace) {
        return
      }

      this.currentPage = 1
      const result = await this.$store.dispatch('workspaceSearch/search', {
        workspaceId: this.currentWorkspace.id,
        searchTerm,
        limit: this.pageSize * this.initialLoadPages,
        offset: 0,
        append: false,
      })

      this.hasMoreResults = result.has_more || false
      this.activeIndex = 0
      this.isSearching = false
    }, 400),

    async loadMoreResults() {
      if (!this.hasMoreResults || this.isLoadingMore || !this.searchTerm) {
        return
      }

      this.isLoadingMore = true
      const offset = this.totalResultCount

      const result = await this.$store.dispatch('workspaceSearch/search', {
        workspaceId: this.currentWorkspace.id,
        searchTerm: this.searchTerm,
        limit: this.pageSize * this.scrollLoadPages,
        offset,
        append: true,
      })

      this.hasMoreResults = result.has_more || false
      this.isLoadingMore = false
    },

    handleScroll(event) {
      const { target } = event
      const { scrollTop, scrollHeight, clientHeight } = target

      const threshold = 100
      const isNearBottom = scrollTop + clientHeight >= scrollHeight - threshold

      if (isNearBottom && this.hasMoreResults && !this.isLoadingMore) {
        this.loadMoreResults()
      }
    },

    handleKeydown(event) {
      this.isKeyboardNavigating = true
      switch (event.key) {
        case 'ArrowDown':
          event.preventDefault()
          this.moveSelection(1)
          break
        case 'ArrowUp':
          event.preventDefault()
          this.moveSelection(-1)
          break
        case 'Enter':
          event.preventDefault()
          this.selectActiveItem()
          break
        case 'Escape':
          this.hide()
          break
      }
    },

    moveSelection(direction) {
      const newIndex = this.activeIndex + direction
      if (newIndex < 0) {
        this.activeIndex = 0
      } else if (newIndex > this.maxIndex) {
        this.activeIndex = this.maxIndex
      } else {
        this.activeIndex = newIndex
      }
      this.scrollToActiveItem()
    },

    scrollToActiveItem() {
      this.$nextTick(() => {
        if (this.activeIndex >= 0 && this.allResults.length > 0) {
          const resultItems = this.$el.querySelectorAll(
            '.workspace-search__result-item'
          )
          const activeItem = resultItems[this.activeIndex]

          if (activeItem) {
            activeItem.scrollIntoView({
              behavior: 'smooth',
              block: 'nearest',
              inline: 'nearest',
            })
          }
        }
      })
    },

    selectActiveItem() {
      if (this.hasResults) {
        if (
          this.activeIndex >= 0 &&
          this.activeIndex < this.allResults.length
        ) {
          this.selectResult(this.allResults[this.activeIndex])
        }
      }
    },

    selectResult(result) {
      const url = this.buildResultUrl(result)
      if (url) {
        this.$router.push(url)
        this.hide()
      }
    },

    buildResultUrl(result) {
      return searchTypeRegistry.buildUrl(result.type, result, {
        store: this.$store,
      })
    },

    getResultIcon(type) {
      return searchTypeRegistry.getIcon(type)
    },

    handleMouseEnter(index) {
      if (!this.isKeyboardNavigating) {
        this.activeIndex = index
      }
    },
  },
}
</script>
