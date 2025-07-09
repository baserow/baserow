<template>
  <div class="data-source-item__wrapper">
    <div class="data-source-item">
      <div class="data-source-item__handle" data-sortable-handle />
      <Presentation
        class="flex-grow-1"
        :title="dataSource.name"
        size="medium"
        :image="!isInError ? image : null"
        :icon="isInError ? 'iconoir-warning-circle' : null"
        :initials="image ? null : '?'"
        :subtitle="subtitle"
        :rounded-icon="false"
        :avatar-color="isInError ? 'red' : 'neutral'"
        @click="
          $hasPermission(
            'builder.page.data_source.update',
            dataSource,
            workspace.id
          ) && $emit('edit', dataSource)
        "
      />
      <div
        v-if="
          $hasPermission(
            'builder.page.data_source.update',
            dataSource,
            workspace.id
          )
        "
        class="data-source-item__actions"
      >
        <ButtonIcon icon="iconoir-edit" @click="$emit('edit', dataSource)" />
        <ButtonIcon
          ref="contextOpener"
          type="secondary"
          icon="iconoir-more-vert"
          @click="
            $refs.dataSourceItemContext.toggle(
              $refs.contextOpener.$el,
              'bottom',
              'right',
              4
            )
          "
        />
      </div>
      <DataSourceItemContext
        ref="dataSourceItemContext"
        :shared="shared"
        @delete="$emit('delete', dataSource)"
        @share="$emit('share', dataSource)"
      />
    </div>
  </div>
</template>

<script>
import DataSourceItemContext from '@baserow/modules/builder/components/dataSource/DataSourceItemContext'

export default {
  name: 'DataSourceItem',
  components: { DataSourceItemContext },
  inject: ['workspace', 'builder'],
  props: {
    dataSource: {
      type: Object,
      required: true,
    },
    shared: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  computed: {
    isInError() {
      return this.dataSourceType?.isInError({ service: this.dataSource })
    },
    dataSourceType() {
      if (!this.dataSource.type) {
        return null
      }
      return this.$registry.get('service', this.dataSource.type)
    },
    integrationType() {
      return this.dataSourceType?.integrationType
    },
    image() {
      return this.integrationType?.image || 'default.png'
    },
    subtitle() {
      return this.dataSourceType
        ? this.dataSourceType.getDescription(this.dataSource, this.builder)
        : this.$t('dataSourceItem.notConfigured')
    },
  },
  methods: {},
}
</script>
