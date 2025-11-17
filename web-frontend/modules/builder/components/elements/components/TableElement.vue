<template>
  <div class="table-element">
    <CollectionElementHeader
      :element="element"
      :style="getStyleOverride('header_button')"
      @filters-changed="adhocFilters = $event"
      @sortings-changed="adhocSortings = $event"
      @search-changed="adhocSearch = $event"
    ></CollectionElementHeader>
    <ABTable
      :fields="fields"
      :rows="rows"
      :content-loading="contentLoading"
      :style="getStyleOverride('table')"
      :orientation="orientation"
    >
      <template #cell-content="{ rowIndex, field, value, row }">
        <!--
        -- We force-self-alignment to `auto` here to prevent some self-positioning
        -- like in buttons or links. we want to position the content through the table
        -- style to be able to override it later. Otherwise we have a conflict between
        -- these two alignments and only the more specific one (the field one)
        -- is respected even if it comes from the main theme.
        -->
        <td
          :key="`${row.__id__}_${field.__id__}`"
          class="ab-table__cell"
          :style="{
            '--force-self-alignment': 'auto',
            ...fieldOverrides[field.id],
          }"
        >
          <div class="ab-table__cell-content">
            <component
              :is="collectionFieldTypes[field.type].component"
              :element="element"
              :field="field"
              :application-context-additions="
                getPerRecordApplicationContextAddition({
                  applicationContext,
                  row,
                  rowIndex,
                  field,
                  allowSameElement: true,
                })
              "
              v-bind="value"
            />
          </div>
        </td>
      </template>
    </ABTable>
    <div class="table-element__footer">
      <ABButton
        v-if="hasMorePage"
        :style="getStyleOverride('button')"
        :disabled="contentLoading || !contentFetchEnabled"
        :loading="contentLoading"
        @click="loadMore()"
      >
        {{ resolvedButtonLoadMoreLabel || $t('tableElement.showMore') }}
      </ABButton>
    </div>
  </div>
</template>

<script>
import element from '@baserow/modules/builder/mixins/element'
import RuntimeFormulaContext from '@baserow/modules/core/runtimeFormulaContext'
import { uuid } from '@baserow/modules/core/utils/string'
import BaserowTable from '@baserow/modules/builder/components/elements/components/BaserowTable'
import collectionElement from '@baserow/modules/builder/mixins/collectionElement'
import { ensureString } from '@baserow/modules/core/utils/validator'
import CollectionElementHeader from '@baserow/modules/builder/components/elements/components/CollectionElementHeader'

export default {
  name: 'TableElement',
  components: { CollectionElementHeader, BaserowTable },
  mixins: [element, collectionElement],
  props: {
    /**
     * @type {Object}
     * @property {int} data_source_id - The collection data source Id we want to
     *   display.
     * @property {Object} fields - The fields of the data source.
     * @property {int} items_per_page - The number of items per page.
     * @property {string} button_color - The color of the button.
     * @property {string} orientation - The orientation for eaceh device.
     */
    element: {
      type: Object,
      required: true,
    },
  },
  computed: {
    fields() {
      if (!this.element.fields) {
        return []
      }
      return this.element.fields.map((field) => ({
        ...field,
        __id__: field.id,
      }))
    },
    rows() {
      if (!this.elementContent) {
        return []
      }
      return this.elementContent.map((row, rowIndex) => {
        const newRow = Object.fromEntries(
          this.fields.map((field) => {
            const { __id__: fieldId, type } = field
            const fieldType = this.collectionFieldTypes[type]
            return [
              fieldId,
              fieldType.getProps(field, {
                resolveFormula: (formula) =>
                  this.resolveRowFormula(formula, rowIndex),
                applicationContext: this.applicationContext,
              }),
            ]
          })
        )
        newRow.__id__ = uuid()
        newRow.__recordId__ = row.__recordId__
        return newRow
      })
    },
    fieldOverrides() {
      return Object.fromEntries(
        this.element.fields.map((field) => {
          const fieldType = this.collectionFieldTypes[field.type]

          return [
            field.id,
            fieldType.getStyleOverride({
              colorVariables: this.colorVariables,
              field,
              theme: this.builder.theme,
            }),
          ]
        })
      )
    },
    collectionFieldTypes() {
      return this.$registry.getAll('collectionField')
    },
    orientation() {
      const device = this.$store.getters['page/getDeviceTypeSelected']
      return this.element.orientation[device]
    },
    resolvedButtonLoadMoreLabel() {
      return ensureString(
        this.resolveFormula(this.element.button_load_more_label)
      )
    },
  },

  methods: {
    resolveRowFormula(formula, index) {
      const formulaContext = new Proxy(
        new RuntimeFormulaContext(
          this.$registry.getAll('builderDataProvider'),
          {
            ...this.applicationContext,
            recordIndexPath: [
              ...this.applicationContext.recordIndexPath,
              index,
            ],
            allowSameElement: true,
          }
        ),
        {
          get(target, prop) {
            return target.get(prop)
          },
        }
      )
      try {
        return ensureString(this.resolveFormula(formula, formulaContext))
      } catch {
        return ''
      }
    },
  },
}
</script>
