<template>
  <ul v-if="!tableLoading" class="header__filter header__filter--full-width">
    <li v-if="dateSettingsAreValid" class="header__filter-item">
      <a
        ref="dateSettingsLink"
        class="header__filter-link"
        @click="showChooseDatesFieldContext"
      >
        <i class="header__filter-icon iconoir-calendar"></i>
        <span class="header__filter-name">
          {{ $t('timelineViewHeader.dateSettings') }}
        </span>
      </a>
      <TimelineDateSettingsHeaderContext
        ref="dateSettingsContext"
        :fields="fields"
        :view="view"
        :read-only="!canChangeDateSettings"
        @refresh="$emit('refresh', $event)"
      >
      </TimelineDateSettingsHeaderContext>
    </li>
    <li v-if="dateSettingsAreValid" class="header__filter-item">
      <a
        ref="customizeContextLink"
        class="header__filter-link"
        @click="
          $refs.customizeContext.toggle(
            $refs.customizeContextLink,
            'bottom',
            'left',
            4
          )
        "
      >
        <i class="header__filter-icon iconoir-list"></i>
        <span class="header__filter-name">{{
          $t('timelineViewHeader.labels')
        }}</span>
      </a>
      <ViewFieldsContext
        ref="customizeContext"
        :database="database"
        :view="view"
        :fields="fields"
        :field-options="fieldOptions"
        :allow-cover-image-field="false"
        @update-all-field-options="updateAllFieldOptions"
        @update-field-options-of-field="updateFieldOptionsOfField"
        @update-order="orderFieldOptions"
      ></ViewFieldsContext>
    </li>
    <li v-if="isDev" class="header__filter-item">
      <div :style="{ display: 'flex', alignItems: 'center', height: '32px' }">
        <Badge color="yellow" indicator>Debug</Badge>
        <span>{{ timezone ? timezone : '' }}</span>
      </div>
    </li>
    <li class="header__filter-item header__filter-item--full-width">
      <ViewSearch
        :view="view"
        :fields="fields"
        :store-prefix="storePrefix"
        :always-hide-rows-not-matching-search="true"
        @refresh="$emit('refresh', $event)"
      ></ViewSearch>
    </li>
  </ul>
</template>

<script>
import { mapState, mapGetters } from 'vuex'

import { notifyIf } from '@baserow/modules/core/utils/error'
import ViewFieldsContext from '@baserow/modules/database/components/view/ViewFieldsContext'
import ViewSearch from '@baserow/modules/database/components/view/ViewSearch'
import timelineViewHelpers from '@baserow_premium/mixins/timelineViewHelpers'
import TimelineDateSettingsHeaderContext from '@baserow_premium/components/views/timeline/TimelineDateSettingsHeaderContext'

export default {
  name: 'TimelineViewHeader',
  components: {
    ViewFieldsContext,
    TimelineDateSettingsHeaderContext,
    ViewSearch,
  },
  mixins: [timelineViewHelpers],
  computed: {
    isDev() {
      return process.env.NODE_ENV === 'development'
    },
    ...mapState({
      tableLoading: (state) => state.table.loading,
    }),
  },
  beforeCreate() {
    this.$options.computed = {
      ...(this.$options.computed || {}),
      ...mapGetters({
        fieldOptions:
          this.$options.propsData.storePrefix +
          'view/timeline/getAllFieldOptions',
      }),
    }
  },
  methods: {
    showChooseDatesFieldContext() {
      this.$refs.dateSettingsContext.toggle(
        this.$refs.dateSettingsLink,
        'bottom',
        'left',
        4
      )
    },
    async updateAllFieldOptions({ newFieldOptions, oldFieldOptions }) {
      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/timeline/updateAllFieldOptions',
          {
            newFieldOptions,
            oldFieldOptions,
            readOnly:
              this.readOnly ||
              !this.$hasPermission(
                'database.table.view.update_field_options',
                this.view,
                this.database.workspace.id
              ),
          }
        )
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
    async updateFieldOptionsOfField({ field, values, oldValues }) {
      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/timeline/updateFieldOptionsOfField',
          {
            field,
            values,
            oldValues,
            readOnly:
              this.readOnly ||
              !this.$hasPermission(
                'database.table.view.update_field_options',
                this.view,
                this.database.workspace.id
              ),
          }
        )
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
    async orderFieldOptions({ order }) {
      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/timeline/updateFieldOptionsOrder',
          {
            order,
            readOnly: this.readOnly,
          }
        )
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
  },
}
</script>
