<template>
  <div
    v-if="
      $hasPermission(
        'database.table.view.list_decoration',
        view,
        database.workspace.id
      )
    "
  >
    <a
      ref="contextLink"
      class="header__filter-link"
      :class="{ 'active active--primary': decoratorCount > 0 }"
      @click="$refs.context.toggle($refs.contextLink, 'bottom', 'left', 4, -16)"
    >
      <i class="header__filter-icon iconoir-palette"></i>
      <span class="header__filter-name">
        {{
          $tc('viewDecorator.decorator', decoratorCount, {
            count: decoratorCount,
          })
        }}
      </span>
    </a>
    <ViewDecoratorContext
      ref="context"
      :database="database"
      :view="view"
      :table="table"
      :fields="fields"
      :read-only="
        readOnly ||
        !$hasPermission(
          'database.table.view.create_decoration',
          view,
          database.workspace.id
        )
      "
      @changed="$emit('changed')"
    ></ViewDecoratorContext>
  </div>
</template>

<script>
import ViewDecoratorContext from '@baserow/modules/database/components/view/ViewDecoratorContext'

export default {
  name: 'ViewDecoratorMenu',
  components: { ViewDecoratorContext },
  props: {
    database: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    view: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
  },
  computed: {
    decoratorCount() {
      return this.view.decorations.filter(({ type }) => {
        return !this.$registry
          .get('viewDecorator', type)
          .isDeactivated(this.database.workspace.id)
      }).length
    },
  },
}
</script>
