<template>
  <div class="repeat-element--container">
    <CollectionElementHeader
      :element="element"
      :style="getStyleOverride('header_button')"
      @filters-changed="adhocFilters = $event"
      @sortings-changed="adhocSortings = $event"
      @search-changed="adhocSearch = $event"
    ></CollectionElementHeader>
    <div
      :class="{
        [`repeat-element--orientation-${element.orientation}`]: true,
      }"
    >
      <!-- If we have any contents to repeat... -->
      <template v-if="elementContent.length > 0">
        <div
          class="repeat-element__repeated-elements"
          :style="repeatedElementsStyles"
        >
          <!-- Iterate over each content -->
          <div v-for="(content, index) in elementContent" :key="content.id">
            <!-- If the container has any children -->
            <template v-if="children.length > 0">
              <!-- Iterate over each child -->
              <template v-for="child in children">
                <!-- The first iteration is editable if we're in editing mode -->
                <ElementPreview
                  v-if="index === 0 && isEditMode"
                  :key="`${child.id}-${index}`"
                  :element="child"
                  :application-context-additions="
                    getPerRecordApplicationContextAddition({
                      applicationContext,
                      row: content,
                      rowIndex: index,
                    })
                  "
                  @move="$emit('move', $event)"
                />
                <!-- Other iterations are not editable -->
                <!-- Override the mode so that any children are in public mode -->
                <PageElement
                  v-else
                  v-show="!isCollapsed"
                  :key="`${child.id}_${index}`"
                  :element="child"
                  :force-mode="isEditMode ? 'public' : mode"
                  :application-context-additions="
                    getPerRecordApplicationContextAddition({
                      applicationContext,
                      row: content,
                      rowIndex: index,
                    })
                  "
                  :class="{
                    'repeat-element__preview': index > 0 && isEditMode,
                  }"
                />
              </template>
            </template>
          </div>
        </div>
        <!-- We have contents, but the container has no children... -->
        <template v-if="children.length === 0 && isEditMode">
          <!-- Give the designer the chance to add child elements -->
          <AddElementZone
            :disabled="elementIsInError && !elementHasSourceOfData"
            :tooltip="addElementErrorTooltipMessage"
            @add-element="showAddElementModal"
          ></AddElementZone>
          <AddElementModal
            ref="addElementModal"
            :page="elementPage"
          ></AddElementModal>
        </template>
      </template>
      <!-- We have no contents to repeat -->
      <template v-else>
        <!-- We have no element content, but do have an adhoc refinements in public mode -->
        <template v-if="(adhocSearch || adhocFilters) && !isEditMode">
          <p class="repeat-element__empty-message">
            {{ $t('repeatElement.emptyState') }}
          </p>
        </template>
        <!-- If we also have no children, allow the designer to add elements -->
        <template v-if="children.length === 0 && isEditMode">
          <AddElementZone
            :disabled="elementIsInError && !elementHasSourceOfData"
            :tooltip="addElementErrorTooltipMessage"
            @add-element="showAddElementModal"
          ></AddElementZone>
          <AddElementModal
            ref="addElementModal"
            :page="elementPage"
          ></AddElementModal>
        </template>
        <!-- We have no contents, but we do have children in edit mode -->
        <template v-else-if="isEditMode">
          <div v-if="contentLoading" class="loading"></div>
          <template v-else>
            <ElementPreview
              v-for="child in children"
              :key="child.id"
              :element="child"
              @move="$emit('move', $event)"
            />
          </template>
        </template>
      </template>
      <div class="repeat-element__footer">
        <ABButton
          v-if="hasMorePage && children.length > 0"
          :style="getStyleOverride('button')"
          :disabled="contentLoading || !contentFetchEnabled"
          :loading="contentLoading"
          @click="loadMore()"
        >
          {{ resolvedButtonLoadMoreLabel || $t('repeatElement.showMore') }}
        </ABButton>
      </div>
    </div>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'

import AddElementZone from '@baserow/modules/builder/components/elements/AddElementZone'
import containerElement from '@baserow/modules/builder/mixins/containerElement'
import collectionElement from '@baserow/modules/builder/mixins/collectionElement'
import AddElementModal from '@baserow/modules/builder/components/elements/AddElementModal'
import ElementPreview from '@baserow/modules/builder/components/elements/ElementPreview'
import PageElement from '@baserow/modules/builder/components/page/PageElement'
import { ensureString } from '@baserow/modules/core/utils/validator'
import { RepeatElementType } from '@baserow/modules/builder/elementTypes'
import CollectionElementHeader from '@baserow/modules/builder/components/elements/components/CollectionElementHeader'
import { ORIENTATIONS } from '@baserow/modules/builder/enums'

export default {
  name: 'RepeatElement',
  components: {
    CollectionElementHeader,
    PageElement,
    ElementPreview,
    AddElementModal,
    AddElementZone,
  },
  mixins: [containerElement, collectionElement],
  props: {
    /**
     * @type {Object}
     * @property {int} data_source_id - The collection data source Id we want to display.
     * @property {int} items_per_page - The number of items per page.
     * @property {str} orientation - The orientation to repeat in (vertical, horizontal).
     * @property {Object} items_per_row - The number of items, per device, which should
     *  be repeated in a row. Only applicable to when the orientation is 'horizontal'.
     * @property {int} horizontal_gap - The amount of space between repeat
     *   elements when the orientation is 'horizontal'.
     * @property {int} vertical_gap - The amount of space between repeat
     *   elements when the orientation is 'vertical'.
     */
    element: {
      type: Object,
      required: true,
    },
  },
  computed: {
    ...mapGetters({ deviceTypeSelected: 'page/getDeviceTypeSelected' }),
    isCollapsed() {
      return this.$store.getters['element/getRepeatElementCollapsed'](
        this.element
      )
    },
    repeatElementIsNested() {
      return this.elementType.hasAncestorOfType(
        this.elementPage,
        this.element,
        RepeatElementType.getType()
      )
    },
    addElementErrorTooltipMessage() {
      if (!this.repeatElementIsNested && this.element.data_source_id === null) {
        return this.$t('repeatElement.missingDataSourceTooltip')
      }
      return this.$t('repeatElement.missingSchemaPropertyTooltip')
    },
    repeatedElementsStyles() {
      // These styles are applied inline as we are unable to provide
      // the CSS rules with the correct `items_per_row` per device. If
      // we add CSS vars to the element, and pass them into the
      // `grid-template-columns` rule's `repeat`, it will cause a repaint
      // following page load when the orientation is horizontal. Initially the
      // page visitor will see repetitions vertically, then suddenly horizontally.
      if (this.element.orientation === ORIENTATIONS.VERTICAL) {
        return {
          display: 'flex',
          'flex-direction': 'column',
          gap: `${this.element.vertical_gap}px ${this.element.horizontal_gap}px`,
        }
      } else {
        return {
          display: 'grid',
          'grid-template-columns': `repeat(${
            this.element.items_per_row[this.deviceTypeSelected]
          }, 1fr)`,
          gap: `${this.element.vertical_gap}px ${this.element.horizontal_gap}px`,
        }
      }
    },
    resolvedButtonLoadMoreLabel() {
      return ensureString(
        this.resolveFormula(this.element.button_load_more_label)
      )
    },
  },
  methods: {
    showAddElementModal() {
      this.$refs.addElementModal.show({
        placeInContainer: null,
        parentElementId: this.element.id,
      })
    },
  },
}
</script>
