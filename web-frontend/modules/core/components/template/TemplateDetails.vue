<template>
  <TemplatePreview
    :template="template"
    :sidebar-width="320"
    class="template-details"
  >
    <template #sidebar="{ applications, page, selectPage, selectApplication }">
      <div class="template-details__sidebar">
        <div v-if="showBack" class="template-details__back">
          <a
            class="template-details__back-link"
            role="button"
            tabindex="0"
            @click="emit('back')"
            @keydown.enter.prevent="emit('back')"
            @keydown.space.prevent="emit('back')"
          >
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
          <div
            v-if="template.description"
            class="template-details__description"
          >
            {{ template.description }}
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
              @selected="selectApplication"
              @selected-page="selectPage"
            ></component>
          </ul>
        </div>
        <div class="template-details__foot">
          <TemplateInstall
            :template="template"
            :workspace="workspace"
            :show-copy-link="!isOwn"
            :latest="isOwn"
            @installed="emit('installed')"
          >
            <template v-if="isOwn" #menu-items="{ hide }">
              <li class="context__menu-item">
                <a
                  class="context__menu-item-link"
                  @click.prevent="edit('details', hide)"
                >
                  <i class="context__menu-item-icon iconoir-edit-pencil"></i>
                  {{ $t('templateDetails.editDetails') }}
                </a>
              </li>
              <li class="context__menu-item">
                <a
                  class="context__menu-item-link"
                  @click.prevent="edit('content', hide)"
                >
                  <i class="context__menu-item-icon iconoir-refresh-double"></i>
                  {{ $t('templateDetails.updateContent') }}
                </a>
              </li>
              <li class="context__menu-item context__menu-item--with-separator">
                <a
                  class="context__menu-item-link context__menu-item-link--delete"
                  @click.prevent="askToDelete(hide)"
                >
                  <i class="context__menu-item-icon iconoir-bin"></i>
                  {{ $t('templateDetails.delete') }}
                </a>
              </li>
            </template>
          </TemplateInstall>
        </div>
      </div>
    </template>
  </TemplatePreview>
</template>

<script setup>
import { useNuxtApp } from '#app'

import TemplatePreview from '@baserow/modules/core/components/template/TemplatePreview'
import TemplateInstall from '@baserow/modules/core/components/template/TemplateInstall'

const props = defineProps({
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
  // Whether the template is one of the user's, opened from "Your templates". The
  // user can then update it, and installs its latest revision.
  isOwn: {
    type: Boolean,
    required: false,
    default: false,
  },
})

// `edit` asks to update the details or the content of the user's template, and
// `delete` to delete it.
const emit = defineEmits(['back', 'installed', 'edit', 'delete'])

const { $registry } = useNuxtApp()

function edit(mode, hideMenu) {
  hideMenu()
  emit('edit', mode)
}

function askToDelete(hideMenu) {
  hideMenu()
  emit('delete', props.template)
}

function sortApplications(applications) {
  return [...applications].sort((a, b) => a.order - b.order)
}

function getApplicationComponent(application) {
  return $registry
    .get('application', application.type)
    .getTemplateSidebarComponent()
}
</script>
