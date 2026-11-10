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
                  v-if="isOwner && !template.listed && !isBlocked"
                  v-tooltip="$t('templateDetails.private')"
                  class="template-details__private iconoir-eye-off"
                ></i>
              </div>
              <Badge
                v-if="isBlocked"
                v-tooltip:[REASON_TOOLTIP_OPTIONS]="shown.reason || null"
                class="template-details__state"
                :color="blockedState.color"
                rounded
                ><i
                  class="template-details__state-icon"
                  :class="blockedState.icon"
                ></i
                >{{ blockedState.label }}</Badge
              >
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
              :template="shown"
              :workspace="workspace"
              :show-copy-link="!ownerActions && !isPrivateLink && !isBlocked"
              :copy-link-url="ownerActions ? privateLinkUrl : null"
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
              <template
                v-if="ownerActions || canBlock"
                #menu-items-end="{ hide }"
              >
                <template v-if="canBlock">
                  <li
                    class="context__menu-item context__menu-item--with-separator"
                  >
                    <a
                      class="context__menu-item-link"
                      @click.prevent="askToBlock(hide)"
                    >
                      <i
                        class="context__menu-item-icon iconoir-warning-triangle"
                      ></i>
                      {{
                        isBlocked
                          ? $t('templateDetails.changeBlockReason')
                          : $t('templatesAdmin.block')
                      }}
                    </a>
                  </li>
                  <li v-if="isBlocked" class="context__menu-item">
                    <a
                      class="context__menu-item-link"
                      @click.prevent="unblock(hide)"
                    >
                      <i class="context__menu-item-icon iconoir-undo"></i>
                      {{ $t('templatesAdmin.unblock') }}
                    </a>
                  </li>
                </template>
                <li
                  v-if="ownerActions"
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
            <RejectTemplateModal
              v-if="canBlock"
              ref="blockModal"
              :template="shown"
              block
              :request="block"
              @done="blocked"
            ></RejectTemplateModal>
          </slot>
        </div>
      </div>
    </template>
  </TemplatePreview>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { useNuxtApp, useRoute, useRuntimeConfig } from '#app'
import { useStore } from 'vuex'

import {
  canMakePrivate,
  canMakePublic,
  getPrivateLinkUrl,
  isOwnTemplate,
  makePublicResubmits,
} from '@baserow/modules/core/utils/userTemplate'
import { isPrivateLinkPage } from '@baserow/modules/core/utils/templatePrivateLink'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { getState } from '@baserow/modules/core/components/template/userTemplateStates'
import { useTemplateReview } from '@baserow/modules/core/composables/useTemplateReview'
import RejectTemplateModal from '@baserow/modules/core/components/admin/templates/RejectTemplateModal'
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
  'moderated',
])

const { $registry, $router, $i18n } = useNuxtApp()
const store = useStore()
const config = useRuntimeConfig()

const isPrivateLink = isPrivateLinkPage(useRoute())
const privateLinkUrl = computed(() =>
  getPrivateLinkUrl(props.template, $router, config.public.publicWebFrontendUrl)
)

function edit(mode, hideMenu) {
  hideMenu()
  emit('edit', mode)
}

const isOwner = computed(() => isOwnTemplate(props.template))

const REASON_TOOLTIP_OPTIONS = {
  contentClasses: ['tooltip__content--expandable', 'template-details__reason'],
}
const moderated = ref(null)
watch(
  () => props.template,
  () => {
    moderated.value = null
  }
)
const shown = computed(() => ({ ...props.template, ...moderated.value }))
const isBlocked = computed(() => shown.value.state === 'blocked')
const blockedState = computed(() => getState('blocked', $i18n.t))

const canBlock = computed(
  () => store.getters['auth/isStaff'] && props.template.type === 'user'
)
const blockModal = ref(null)
const { decide } = useTemplateReview()

function askToBlock(hideMenu) {
  hideMenu()
  blockModal.value.show()
}

function block(template, reason) {
  return decide(template, 'block', reason)
}

function moderate(row) {
  moderated.value = { state: row.state, reason: row.reason }
  emit('moderated')
}

async function unblock(hideMenu) {
  hideMenu()
  try {
    const row = await decide(shown.value, 'unblock')
    if (row) {
      moderate(row)
    }
  } catch (error) {
    notifyIf(error, 'template')
  }
}

function blocked(id, row) {
  if (!row) {
    return
  }
  const name = props.template.name
  store.dispatch(
    'toast/success',
    isBlocked.value
      ? { title: $i18n.t('templateDetails.blockReasonChangedTitle', { name }) }
      : {
          title: $i18n.t('templateDetails.blockedTitle', { name }),
          message: $i18n.t('templateDetails.blockedDescription'),
        }
  )
  moderate(row)
}

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
