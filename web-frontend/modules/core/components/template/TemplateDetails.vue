<template>
  <TemplatePreview
    :template="template"
    :sidebar-width="320"
    class="template-details"
  >
    <template #sidebar="{ applications, page, selectPage }">
      <div class="template-details__sidebar">
        <div v-if="showBack" class="template-details__back">
          <a class="template-details__back-link" @click="emit('back')">
            <i class="iconoir-nav-arrow-left"></i>
            {{ $t('templateDetails.back') }}
          </a>
        </div>
        <div class="template-details__info">
          <div class="template-details__title">
            <div class="template-details__icon">
              <i :class="template.icon || 'iconoir-view-grid'"></i>
            </div>
            <div class="template-details__name">{{ template.name }}</div>
          </div>
          <div v-if="categories.length" class="template-details__categories">
            <span
              v-for="category in categories"
              :key="category.id"
              class="template-details__category"
              >{{ category.name }}</span
            >
          </div>
        </div>
        <div class="template-details__contents">
          <div class="template-details__contents-title">
            {{ $t('templateDetails.contents') }}
          </div>
          <ul class="tree">
            <component
              :is="getApplicationComponent(application)"
              v-for="application in sortApplications(applications)"
              :key="application.id"
              :application="application"
              :page="page"
              @selected="selectApplication(applications, $event)"
              @selected-page="selectPage"
            ></component>
          </ul>
        </div>
        <div class="template-details__foot">
          <TemplateInstall
            :template="template"
            :workspace="workspace"
            @installed="emit('installed')"
          ></TemplateInstall>
        </div>
      </div>
    </template>
  </TemplatePreview>
</template>

<script setup>
import { useNuxtApp } from '#app'

import TemplatePreview from '@baserow/modules/core/components/template/TemplatePreview'
import TemplateInstall from '@baserow/modules/core/components/template/TemplateInstall'

defineProps({
  template: {
    type: Object,
    required: true,
  },
  // The categories the template is listed in.
  categories: {
    type: Array,
    required: false,
    default: () => [],
  },
  // The workspace the template is installed into by default.
  workspace: {
    type: Object,
    required: false,
    default: null,
  },
  showBack: {
    type: Boolean,
    required: false,
    default: false,
  },
})

const emit = defineEmits(['back', 'installed'])

const { $registry } = useNuxtApp()

function sortApplications(applications) {
  return [...applications].sort((a, b) => a.order - b.order)
}

function getApplicationComponent(application) {
  return $registry
    .get('application', application.type)
    .getTemplateSidebarComponent()
}

function selectApplication(applications, application) {
  applications.forEach((app) => {
    app._.selected = application.id === app.id
  })
}
</script>
