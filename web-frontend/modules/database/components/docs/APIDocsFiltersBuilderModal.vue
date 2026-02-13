<template>
  <Modal ref="modal" :wide="true">
    <h2 class="box__title">{{ $t('apiDocsFiltersBuilderModal.title') }}</h2>
    <div class="control margin-bottom-2">
      <div class="control__elements">
        <Checkbox v-model="mutableUserFieldNames">{{
          $t('apiDocsFiltersBuilderModal.userFieldNames')
        }}</Checkbox>
      </div>
    </div>
    <div class="control margin-bottom-2">
      <label class="control__label control__label--small">{{
        $t('apiDocsFiltersBuilderModal.json')
      }}</label>
      <div class="control__description">
        <span class="position-relative">
          <a
            @click.prevent="
              ;[copyToClipboard(JSONFilters), $refs.copiedJSON.show()]
            "
            >{{ $t('action.copyToClipboard') }}</a
          >
          <Copied ref="copiedJSON"></Copied>
        </span>
      </div>
      <div class="control__elements">
        <pre
          class="api-docs__example-content"
        ><code>{{ JSONFilters }}</code></pre>
      </div>
    </div>
    <div class="control margin-bottom-2">
      <label class="control__label control__label--small">{{
        $t('apiDocsFiltersBuilderModal.queryParameter')
      }}</label>
      <div class="control__description">
        <span class="position-relative">
          <a
            @click.prevent="
              ;[
                copyToClipboard(encodedJSONFilters),
                $refs.copiedEncodedJSON.show(),
              ]
            "
            >{{ $t('action.copyToClipboard') }}</a
          >
          <Copied ref="copiedEncodedJSON"></Copied>
        </span>
      </div>
      <div class="control__elements">
        <pre
          class="api-docs__example-content"
        ><code>{{ encodedJSONFilters }}</code></pre>
      </div>
    </div>
    <div class="margin-bottom-2">
      <ViewFieldConditionsForm
        v-if="view.filters.length > 0"
        :filters="view.filters"
        :filter-groups="view.filter_groups"
        :filter-type="view.filter_type"
        :fields="fields"
        :view="view"
        :disable-filter="false"
        :read-only="false"
        :full-width="true"
        :sorted="true"
        :add-condition-string="$t('viewFilterContext.addFilter')"
        :add-condition-group-string="$t('viewFilterContext.addFilterGroup')"
        @add-filter="addFilter"
        @add-filter-group="addFilter"
        @delete-filter="deleteFilter"
        @update-filter="updateFilter"
        @update-filter-type="updateFilterType"
        @delete-filter-group="deleteFilterGroup"
      />
    </div>
    <div class="flex">
      <a class="filters__add" @click.prevent="addFilter()">
        <i class="filters__add-icon iconoir-plus"></i>
        {{ $t('viewFilterContext.addFilter') }}</a
      >
      <a
        class="filters__add"
        @click.prevent="addFilter({ filterGroupId: uuid() })"
      >
        <i class="filters__add-icon iconoir-plus"></i>
        {{ $t('viewFilterContext.addFilterGroup') }}</a
      >
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import ViewFieldConditionsForm from '@baserow/modules/database/components/view/ViewFieldConditionsForm'
import {
  populateView,
  populateFilter,
  populateFilterGroup,
} from '@baserow/modules/database/store/view'
import { GridViewType } from '@baserow/modules/database/viewTypes'
import { uuid } from '@baserow/modules/core/utils/string'
import { hasCompatibleFilterTypes } from '@baserow/modules/database/utils/field'
import { createFiltersTree } from '@baserow/modules/database/utils/view'
import { copyToClipboard } from '@baserow/modules/database/utils/clipboard'
import { clone } from '@baserow/modules/core/utils/object'

export default {
  name: 'APIDocsFiltersBuilderModal',
  components: { ViewFieldConditionsForm },
  mixins: [modal],
  props: {
    userFieldNames: {
      type: Boolean,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
  },
  data() {
    return {
      view: null,
      mutableUserFieldNames: this.userFieldNames,
    }
  },
  computed: {
    JSONFilters() {
      const filters = clone(this.view.filters)

      // If user field names is true, then the query parameter doesn't accept field ids
      // but rather the field name.
      if (this.mutableUserFieldNames) {
        filters.map((filter) => {
          const field = this.fields.find((f) => f.id === filter.field)
          filter.field = field.name
          return filter
        })
      }

      const filterTree = createFiltersTree(
        this.view.filter_type,
        filters,
        this.view.filter_groups
      )
      if (filterTree.hasFilters()) {
        const serializedTree = filterTree.getFiltersTreeSerialized()
        return JSON.stringify(serializedTree)
      }
      return ''
    },
    encodedJSONFilters() {
      let params = '?'

      if (this.mutableUserFieldNames) {
        params += 'user_field_names=true&'
      }

      return params + 'filters=' + encodeURIComponent(this.JSONFilters)
    },
  },
  created() {
    this.view = populateView(
      {
        type: GridViewType.getType(),
        filters: [this.getNewFilterObject(null)],
        filter_groups: [],
        filter_type: 'AND',
      },
      this.$registry
    )
  },
  methods: {
    uuid,
    copyToClipboard,
    getNewFilterObject(filterGroupId, parentGroupId = null) {
      const createNewFilterGroup =
        filterGroupId &&
        this.view.filter_groups.findIndex(
          (group) => group.id === filterGroupId
        ) === -1

      if (createNewFilterGroup) {
        this.view.filter_groups.push(
          populateFilterGroup({
            id: filterGroupId,
            filter_type: 'AND',
            parent_group: parentGroupId,
          })
        )
      }

      const viewFilterTypes = this.$registry.getAll('viewFilter')
      const firstField = this.fields
        .slice()
        .find((field) => hasCompatibleFilterTypes(field, viewFilterTypes))
      const firstType = Object.values(viewFilterTypes).find(
        (viewFilterType) => {
          return viewFilterType.fieldIsCompatible(firstField)
        }
      )

      return populateFilter({
        id: uuid(),
        group: filterGroupId,
        field: firstField.id,
        type: firstType.type,
        value: '',
      })
    },
    addFilter({ filterGroupId = null, parentGroupId = null } = {}) {
      this.view.filters.push(
        this.getNewFilterObject(filterGroupId, parentGroupId)
      )
    },
    updateFilter({ filter, values }) {
      values.preload_values = {}
      Object.assign(filter, filter, values)
    },
    deleteFilter(filter) {
      const index = this.view.filters.findIndex((f) => f.id === filter.id)
      this.view.filters.splice(index, 1)
    },
    updateFilterType({ filterGroup, value }) {
      if (filterGroup === undefined) {
        this.view.filter_type = value
      } else {
        filterGroup.filter_type = value
      }
    },
    deleteFilterGroup({ group }) {
      const index = this.view.filter_groups.findIndex((g) => g.id === group.id)
      this.view.filters = this.view.filters.filter(
        (filter) => filter.group !== group.id
      )
      this.view.filter_groups.splice(index, 1)
    },
  },
}
</script>
