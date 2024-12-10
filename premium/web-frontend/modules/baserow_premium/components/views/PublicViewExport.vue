<template>
  <li
    v-if="view.allow_public_export"
    class="header__filter-item header__filter-item--no-margin-left"
  >
    <a
      ref="target"
      class="header__filter-link"
      @click="$refs.context.toggle($event.target, 'bottom', 'left', 4)"
    >
      <i class="header__filter-icon baserow-icon-more-vertical"></i>
    </a>
    <Context ref="context">
      <ul class="context__menu">
        <li class="context__menu-item">
          <a class="context__menu-item-link" @click="exportView()">
            <i class="context__menu-item-icon iconoir-share-ios"></i>
            {{ $t('publicViewExport.export') }}
          </a>
        </li>
      </ul>
    </Context>
  </li>
</template>

<script>
export default {
  name: 'PublicViewExport',
  props: {
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    view: {
      type: Object,
      required: true,
    },
    isPublicView: {
      type: Boolean,
      required: true,
    },
  },
}
</script>
