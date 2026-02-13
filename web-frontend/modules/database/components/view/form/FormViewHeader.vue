<template>
  <ul v-if="!tableLoading" class="header__filter header__filter--full-width">
    <li
      v-if="
        $hasPermission(
          'database.table.view.update',
          view,
          database.workspace.id
        )
      "
      class="header__filter-item"
    >
      <a
        v-if="!readOnly"
        ref="modeContextLink"
        class="header__filter-link"
        @click="
          $refs.modeContext.toggle($refs.modeContextLink, 'bottom', 'left', 4)
        "
      >
        <i class="header__filter-icon iconoir-palette"></i>
        <span class="header__filter-name">{{ $t('formViewHeader.mode') }}</span>
      </a>
      <FormViewModeContext
        ref="modeContext"
        :database="database"
        :view="view"
      ></FormViewModeContext>
    </li>
    <li class="header__filter-item">
      <a
        v-if="!readOnly"
        :href="formUrl"
        target="_blank"
        rel="noopener"
        class="header__filter-link"
      >
        <i class="header__filter-icon iconoir-eye-empty"></i>
        <span class="header__filter-name">{{
          $t('formViewHeader.preview')
        }}</span>
      </a>
    </li>
  </ul>
</template>

<script>
import { mapState } from 'vuex'

import formViewHelpers from '@baserow/modules/database/mixins/formViewHelpers'
import FormViewModeContext from '@baserow/modules/database/components/view/form/FormViewModeContext'

export default {
  name: 'FormViewHeader',
  components: { FormViewModeContext },
  mixins: [formViewHelpers],
  props: {
    database: {
      type: Object,
      required: true,
    },
    view: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
  },
  computed: {
    formUrl() {
      return (
        this.$config.public.publicWebFrontendUrl +
        this.$router.resolve({
          name: this.$registry.get('view', this.view.type).getPublicRoute(),
          params: { slug: this.view.slug },
        }).href
      )
    },
    ...mapState({
      tableLoading: (state) => state.table.loading,
    }),
  },
}
</script>
