<template>
  <TemplatePreview
    :template="template"
    :sidebar-width="320"
    :load-error-handler="loadErrorHandler"
    class="template-details"
    @loaded="loaded"
  >
    <template #sidebar="{ applications, page, selectPage, selectApplication }">
      <div class="template-details__sidebar">
        <div v-if="showBack" class="template-details__back">
          <a
            ref="backLink"
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
            <div class="template-details__heading">
              <div class="template-details__name">{{ template.name }}</div>
              <div v-if="template.author_name" class="template-details__author">
                <Avatar
                  :initials="template.author_name.charAt(0).toUpperCase()"
                  size="small"
                  rounded
                ></Avatar>
                <span class="template-details__author-name">{{
                  isOwner ? $t('templateDetails.you') : template.author_name
                }}</span>
                <i
                  v-if="isOwner && !template.listed"
                  v-tooltip="$t('templateDetails.private')"
                  class="template-details__private iconoir-eye-off"
                ></i>
              </div>
            </div>
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
          <slot name="foot">
            <TemplateInstall
              :template="template"
              :workspace="workspace"
              :show-copy-link="!ownerActions"
              :latest="ownerActions || isOwner"
              @installed="emit('installed')"
              @outdated="emit('outdated')"
            >
              <template v-if="ownerActions" #menu-items="{ hide }">
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
                    <i
                      class="context__menu-item-icon iconoir-refresh-double"
                    ></i>
                    {{ $t('templateDetails.updateContent') }}
                  </a>
                </li>
                <li v-if="canMakePublic(template)" class="context__menu-item">
                  <a
                    class="context__menu-item-link"
                    @click.prevent="changeVisibility('make-public', hide)"
                  >
                    <i class="context__menu-item-icon iconoir-eye-empty"></i>
                    {{
                      makePublicResubmits(template)
                        ? $t('templateDetails.submitForReviewAgain')
                        : $t('templateDetails.makePublic')
                    }}
                  </a>
                </li>
                <li v-if="canMakePrivate(template)" class="context__menu-item">
                  <a
                    class="context__menu-item-link"
                    @click.prevent="changeVisibility('make-private', hide)"
                  >
                    <i class="context__menu-item-icon iconoir-eye-off"></i>
                    {{ $t('templateDetails.makePrivate') }}
                  </a>
                </li>
              </template>
              <template v-if="ownerActions" #menu-items-end="{ hide }">
                <li
                  class="context__menu-item context__menu-item--with-separator"
                >
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
          </slot>
        </div>
      </div>
    </template>
  </TemplatePreview>
</template>

<script setup>
import { computed, nextTick, ref } from 'vue'
import { useNuxtApp } from '#app'

import {
  canMakePrivate,
  canMakePublic,
  isOwnTemplate,
  makePublicResubmits,
} from '@baserow/modules/core/utils/userTemplate'
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
  ownerActions: {
    type: Boolean,
    required: false,
    default: false,
  },
  loadErrorHandler: {
    type: Function,
    required: false,
    default: null,
  },
})

const emit = defineEmits([
  'loaded',
  'back',
  'installed',
  'outdated',
  'edit',
  'delete',
  'make-public',
  'make-private',
])

const { $registry } = useNuxtApp()

function edit(mode, hideMenu) {
  hideMenu()
  emit('edit', mode)
}

const isOwner = computed(() => isOwnTemplate(props.template))

function changeVisibility(event, hideMenu) {
  hideMenu()
  emit(event, props.template)
}

function askToDelete(hideMenu) {
  hideMenu()
  emit('delete', props.template)
}

const backLink = ref(null)
let focusWanted = false

function focus() {
  focusWanted = true
  focusBackLink()
}

function loaded(succeeded) {
  emit('loaded', succeeded)
  focusBackLink()
}

async function focusBackLink() {
  await nextTick()
  if (focusWanted) {
    backLink.value?.focus()
    focusWanted = document.activeElement !== backLink.value
  }
}

defineExpose({ focus })

function sortApplications(applications) {
  return [...applications].sort((a, b) => a.order - b.order)
}

function getApplicationComponent(application) {
  return $registry
    .get('application', application.type)
    .getTemplateSidebarComponent()
}
</script>
