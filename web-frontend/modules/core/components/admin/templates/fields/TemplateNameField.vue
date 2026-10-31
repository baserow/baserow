<template>
  <div class="templates-admin-name">
    <div class="templates-admin-name__icon">
      <i :class="row.icon || 'iconoir-view-grid'"></i>
    </div>
    <div class="templates-admin-name__text">
      <div class="templates-admin-name__title">
        <div class="templates-admin-name__name" :title="row.name">
          {{ row.name }}
        </div>
        <Badge v-if="showsListed(row)" color="neutral" rounded>{{
          $t('userTemplateList.stateListed')
        }}</Badge>
      </div>
      <div
        v-if="row.description"
        class="templates-admin-name__description"
        :title="row.description"
      >
        {{ row.description }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { showsListed } from '@baserow/modules/core/components/template/userTemplateStates'

defineProps({
  row: {
    type: Object,
    required: true,
  },
})
</script>
