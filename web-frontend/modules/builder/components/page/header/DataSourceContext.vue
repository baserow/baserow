<template>
  <Context
    :class="{ 'context--loading-overlay': state === 'loading' }"
    max-height-if-outside-viewport
    @shown="shown"
  >
    <div
      v-if="sharedDataSources.length > 0 || dataSources.length > 0"
      class="data-source-context__container"
    >
      <div
        v-if="state === 'loaded'"
        v-auto-overflow-scroll
        class="data-source-context__content"
      >
        <div
          v-if="sharedDataSources.length > 0"
          class="data-source-context__content-section"
        >
          <div class="data-source-context__content-section-title">
            {{ $t('dataSourceContext.sharedDataSourceTitle') }}
          </div>
          <div class="data-source-context__content-section-description">
            {{ $t('dataSourceContext.sharedDataSourceDescription') }}
          </div>
          <div class="data-source-context__items">
            <DataSourceItem
              v-for="dataSource in sharedDataSources"
              :key="dataSource.id"
              v-sortable="{
                id: dataSource.id,
                update: orderDS(true),
                handle: '[data-sortable-handle]',
              }"
              :data-source="dataSource"
              shared
              @delete="deleteDataSource($event)"
              @edit="editDataSource($event)"
              @share="moveDataSourceToPage($event, sharedPage, page)"
            />
          </div>
        </div>
        <div
          v-if="dataSources.length > 0"
          class="data-source-context__content-section"
        >
          <div class="data-source-context__content-section-title">
            {{ $t('dataSourceContext.pageDataSourceTitle') }}
          </div>
          <div class="data-source-context__content-section-description">
            {{ $t('dataSourceContext.pageDataSourceDescription') }}
          </div>
          <div class="data-source-context__items">
            <DataSourceItem
              v-for="dataSource in dataSources"
              :key="dataSource.id"
              v-sortable="{
                id: dataSource.id,
                update: orderDS(false),
                handle: '[data-sortable-handle]',
              }"
              :data-source="dataSource"
              @delete="deleteDataSource($event)"
              @edit="editDataSource($event)"
              @share="moveDataSourceToPage($event, page, sharedPage)"
            />
          </div>
        </div>
      </div>
      <div class="context__footer">
        <ButtonText
          v-if="
            $hasPermission(
              'builder.page.create_data_source',
              page,
              workspace.id
            )
          "
          icon="iconoir-plus"
          :loading="creationInProgress"
          @click="createDataSource()"
        >
          {{ $t('dataSourceContext.addDataSource') }}
        </ButtonText>
      </div>
    </div>

    <template v-else>
      <div class="data-source-context__none">
        <div class="data-source-context__none-title">
          {{ $t('dataSourceContext.noDataSourceTitle') }}
        </div>
        <div class="data-source-context__none-description">
          {{ $t('dataSourceContext.noDataSourceMessage') }}
        </div>
        <Button
          v-if="
            $hasPermission(
              'builder.page.create_data_source',
              page,
              workspace.id
            )
          "
          icon="iconoir-plus"
          type="secondary"
          :loading="creationInProgress"
          @click="createDataSource()"
        >
          {{ $t('dataSourceContext.addDataSource') }}
        </Button>
      </div>
    </template>
    <DataSourceCreateEditModal
      v-if="editModalVisible"
      :key="currentDataSourceId"
      ref="dataSourceCreateEditModal"
      :data-source-id="currentDataSourceId"
      @hidden="onHide"
    />
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'
import DataSourceCreateEditModal from '@baserow/modules/builder/components/dataSource/DataSourceCreateEditModal'
import DataSourceItem from '@baserow/modules/builder/components/dataSource/DataSourceItem'
import { mapActions } from 'vuex'
import { ELEMENT_EVENTS } from '@baserow/modules/builder/enums'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'DataSourceContext',
  components: { DataSourceItem, DataSourceCreateEditModal },
  mixins: [context],
  inject: ['workspace', 'builder'],
  props: {
    page: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      state: 'loaded',
      creationInProgress: false,
      currentDataSourceId: null,
      editModalVisible: false,
    }
  },
  computed: {
    integrations() {
      return this.$store.getters['integration/getIntegrations'](this.builder)
    },
    dataSources() {
      return this.$store.getters['dataSource/getPageDataSources'](this.page)
    },
    sharedPage() {
      return this.$store.getters['page/getSharedPage'](this.builder)
    },
    sharedDataSources() {
      return this.$store.getters['dataSource/getPageDataSources'](
        this.sharedPage
      )
    },
    allDataSources() {
      return [...this.dataSources, ...this.sharedDataSources]
    },
    currentDataSource() {
      return this.allDataSources.find(
        ({ id }) => id === this.currentDataSourceId
      )
    },
    elements() {
      return this.$store.getters['element/getElementsOrdered'](this.page)
    },
  },
  methods: {
    ...mapActions({
      actionFetchIntegrations: 'integration/fetch',
      actionCreateDataSource: 'dataSource/create',
      actionMoveDataSourceToPage: 'dataSource/moveToPage',
      actionMoveDataSource: 'dataSource/move',
      actionDeleteDataSource: 'dataSource/delete',
    }),
    async shown() {
      try {
        // We fetch the integrations on load to make sure we have the last version
        // of the database/table/fields.
        await Promise.all([
          this.actionFetchIntegrations({
            application: this.builder,
          }),
        ])
      } catch (error) {
        notifyIf(error)
      }
    },
    onHide() {
      this.editModalVisible = false
      this.currentDataSourceId = null
    },
    orderDS(shared) {
      return async (newOrder, oldOrder, movedId, beforeId) => {
        try {
          await this.actionMoveDataSource({
            page: shared ? this.sharedPage : this.page,
            dataSourceId: movedId,
            beforeDataSourceId: beforeId,
          })
        } catch (error) {
          notifyIf(error)
        }
      }
    },
    async createDataSource() {
      this.currentDataSourceId = null
      this.editModalVisible = true
      await this.$nextTick()
      this.$refs.dataSourceCreateEditModal.show()
    },
    async deleteDataSource(dataSource) {
      const page =
        dataSource.page_id === this.page.id ? this.page : this.sharedPage
      try {
        await this.actionDeleteDataSource({
          page,
          dataSourceId: dataSource.id,
        })
        this.$store.dispatch('dataSourceContent/clearDataSourceContent', {
          page,
          dataSourceId: dataSource.id,
        })
        // Trigger element event listener
        this.$store.dispatch('element/emitElementEvent', {
          event: ELEMENT_EVENTS.DATA_SOURCE_REMOVED,
          elements: this.elements,
          dataSourceId: dataSource.id,
          builder: this.builder,
        })
      } catch (error) {
        notifyIf(error)
      }
    },
    async editDataSource(dataSource) {
      this.currentDataSourceId = dataSource.id
      this.editModalVisible = true
      await this.$nextTick()
      this.$refs.dataSourceCreateEditModal.show()
    },
    async moveDataSourceToPage(dataSource, pageSource, pageDest) {
      try {
        await this.actionMoveDataSourceToPage({
          pageSource,
          pageDest,
          dataSourceId: dataSource.id,
        })
        this.$store.dispatch('element/emitElementEvent', {
          event: ELEMENT_EVENTS.DATA_SOURCE_AFTER_UPDATE,
          elements: this.elements,
          dataSourceId: dataSource.id,
          builder: this.builder,
        })
      } catch (error) {
        notifyIf(error)
      }
    },
  },
}
</script>
