<template>
  <Modal wide v-on="$listeners">
    <h2 class="box__title">
      {{
        create
          ? $t('dataSourceCreateEditModal.createTitle')
          : $t('dataSourceCreateEditModal.editTitle')
      }}
    </h2>
    <div>
      <Error :error="error"></Error>

      <Alert v-if="isShared">
        {{ $t('dataSourceCreateEditModal.sharedWarning') }}
      </Alert>

      <DataSourceForm
        ref="dataSourceForm"
        :data-source="dataSource"
        :builder="builder"
        :page="dataSourcePage"
        :default-values="dataSource"
        :integrations="integrations"
        :create="create"
        :application-context-additions="{
          page: dataSourcePage,
          dataSource: dataSource,
        }"
        @values-changed="onValuesChanged"
        @submitted="onFormSubmit($event)"
      />

      <div class="actions">
        <ButtonText
          type="secondary"
          icon="iconoir-nav-arrow-left"
          @click.prevent="hide()"
        >
          {{ $t('action.back') }}
        </ButtonText>
        <Button
          size="large"
          :loading="loading"
          :disabled="loading || !changed || $refs.dataSourceForm.v$.$anyError"
          @click.prevent="$refs.dataSourceForm.submit()"
        >
          {{ create ? $t('action.create') : $t('action.save') }}
        </Button>
      </div>
    </div>
  </Modal>
</template>

<script>
import DataSourceForm from '@baserow/modules/builder/components/dataSource/DataSourceForm'
import { mapActions } from 'vuex'
import _ from 'lodash'
import error from '@baserow/modules/core/mixins/error'
import modal from '@baserow/modules/core/mixins/modal'
import { ELEMENT_EVENTS } from '@baserow/modules/builder/enums'

export default {
  name: 'DataSourceCreateEditModal',
  components: { DataSourceForm },

  mixins: [modal, error],
  provide() {
    // I know, it's not the page of the element but it's injected into the
    // ApplicationBuilderFormulaInput for data source loading states,
    // and we need the right page which can be in fact the data source page in this
    // case, so it works.
    // May be we could change the name of the elementPage but it would be only for
    // this exception.
    return { elementPage: this.dataSourcePage }
  },
  inject: ['builder', 'currentPage'],
  props: {
    dataSourceId: { type: Number, required: false, default: null },
  },
  data() {
    return {
      loading: false,
      actualDataSourceId: this.dataSourceId,
      changed: false,
    }
  },
  computed: {
    dataSources() {
      return this.$store.getters['dataSource/getPageDataSources'](
        this.currentPage
      )
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
    create() {
      return !this.actualDataSourceId
    },
    isShared() {
      return !this.create && this.dataSource?.page_id === this.sharedPage.id
    },
    dataSource() {
      if (this.create) {
        return undefined
      }
      return this.allDataSources.find(
        ({ id }) => id === this.actualDataSourceId
      )
    },
    integrations() {
      return this.$store.getters['integration/getIntegrations'](this.builder)
    },
    // We don't use the provided page here because it depends on the data source being
    // edited. Sometimes it's the shared page.
    dataSourcePage() {
      if (!this.dataSource) {
        return this.currentPage
      }
      return this.$store.getters['page/getById'](
        this.builder,
        this.dataSource.page_id
      )
    },
    elements() {
      // This is used when we want to dispatch the data source update
      return [
        ...this.$store.getters['element/getElementsOrdered'](this.currentPage),
        ...this.$store.getters['element/getElementsOrdered'](this.sharedPage),
      ]
    },
  },
  methods: {
    ...mapActions({
      actionFetchIntegrations: 'integration/fetch',
      actionCreateDataSource: 'dataSource/create',
      actionUpdateDataSource: 'dataSource/update',
    }),
    onValuesChanged(values) {
      if (!this.actualDataSourceId) {
        this.changed = true
        return
      }
      const differences = Object.entries(values).filter(
        ([key, value]) => !_.isEqual(value, this.dataSource[key])
      )

      if (differences.length) {
        this.changed = true
      }
    },
    async onFormSubmit(values) {
      this.loading = true
      this.hideError()
      let saved = false
      try {
        if (this.create) {
          const createdDataSource = await this.actionCreateDataSource({
            page: this.currentPage,
            values,
          })
          this.actualDataSourceId = createdDataSource.id
        } else {
          const differences = Object.fromEntries(
            Object.entries(values).filter(
              ([key, value]) => !_.isEqual(value, this.dataSource[key])
            )
          )

          const updatedDataSource = await this.actionUpdateDataSource({
            page: this.dataSourcePage,
            dataSourceId: this.dataSource.id,
            values: differences,
          })
          this.$emit('updated', updatedDataSource)
          // Send data source update element event
          this.$store.dispatch('element/emitElementEvent', {
            event: ELEMENT_EVENTS.DATA_SOURCE_AFTER_UPDATE,
            elements: this.elements,
            dataSourceId: this.dataSource.id,
            builder: this.builder,
          })
          saved = true
        }
        this.changed = false
      } catch (error) {
        this.handleError(error)
      } finally {
        this.loading = false
        await this.$nextTick()
        this.$refs.dataSourceForm?.reset()
      }
      if (saved) {
        this.hide()
      }
    },
  },
}
</script>
