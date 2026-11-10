<template>
  <Context ref="contextRef" overflow-scroll max-height-if-outside-viewport>
    <ul v-if="template" class="context__menu">
      <li
        v-for="item in items"
        :key="item.name"
        class="context__menu-item"
        :class="{ 'context__menu-item--with-separator': item.separator }"
      >
        <a
          class="context__menu-item-link"
          :class="{
            'context__menu-item-link--delete': ITEMS[item.name].danger,
            'context__menu-item-link--loading':
              item.name === 'download' && isDownloading(template),
          }"
          @click.prevent="ACTIONS[item.name]()"
        >
          <i class="context__menu-item-icon" :class="ITEMS[item.name].icon"></i>
          {{ $t(ITEMS[item.name].label) }}
          <Copied v-if="item.name === 'copyLink'" :ref="setCopied"></Copied>
        </a>
      </li>
    </ul>
  </Context>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter, useRuntimeConfig } from '#app'

import { useTemplateReview } from '@baserow/modules/core/composables/useTemplateReview'
import { useUserTemplateDownload } from '@baserow/modules/core/composables/useUserTemplateDownload'
import { useCopyLink } from '@baserow/modules/core/composables/useCopyLink'
import { notifyIf } from '@baserow/modules/core/utils/error'

const TEMPLATE_ADMIN_MENU_ITEMS = {
  in_review: [
    { name: 'download' },
    { name: 'block', separator: true },
    { name: 'delete', separator: true },
  ],
  public: [
    { name: 'view' },
    { name: 'copyLink' },
    { name: 'download' },
    { name: 'unlist', separator: true },
    { name: 'block' },
    { name: 'delete', separator: true },
  ],
  rejected: [
    { name: 'approve' },
    { name: 'download', separator: true },
    { name: 'block', separator: true },
    { name: 'delete', separator: true },
  ],
  blocked: [
    { name: 'preview' },
    { name: 'download' },
    { name: 'unblock', separator: true },
    { name: 'delete', separator: true },
  ],
}

const ITEMS = {
  view: { label: 'templatesAdmin.viewInTemplates', icon: 'iconoir-view-grid' },
  preview: { label: 'templatesAdmin.preview', icon: 'iconoir-eye-empty' },
  copyLink: { label: 'templateInstall.copyLink', icon: 'iconoir-link' },
  download: { label: 'templateInstall.download', icon: 'iconoir-download' },
  unlist: {
    label: 'templatesAdmin.unlistFromBrowser',
    icon: 'iconoir-eye-off',
  },
  approve: { label: 'templatesAdmin.approveAfterAll', icon: 'iconoir-check' },
  block: { label: 'templatesAdmin.block', icon: 'iconoir-warning-triangle' },
  unblock: { label: 'templatesAdmin.unblock', icon: 'iconoir-undo' },
  delete: { label: 'templatesAdmin.delete', icon: 'iconoir-bin', danger: true },
}

const props = defineProps({
  template: {
    type: Object,
    default: null,
  },
})

const emit = defineEmits([
  'view',
  'preview',
  'unlist',
  'block',
  'delete',
  'changed',
])

const router = useRouter()
const config = useRuntimeConfig()
const { decide } = useTemplateReview()
const { isDownloading, download } = useUserTemplateDownload()
const { copyLink } = useCopyLink()

const contextRef = ref(null)
let copied = null

const items = computed(() =>
  (TEMPLATE_ADMIN_MENU_ITEMS[props.template?.state] ?? []).filter(
    ({ name }) => name !== 'approve' || props.template.can_approve
  )
)

function setCopied(component) {
  copied = component
}

const ACTIONS = {
  view() {
    hide()
    emit('view', props.template)
  },
  preview() {
    hide()
    emit('preview', props.template)
  },
  copyLink() {
    return copyLink(
      new URL(
        router.resolve({
          name: 'template',
          params: { slug: props.template.slug },
        }).href,
        config.public.publicWebFrontendUrl
      ).toString(),
      copied
    )
  },
  async download() {
    const template = props.template
    const onOutdated = () => emit('changed', template.id)
    if (
      (await download(template, { onOutdated })) &&
      props.template?.id === template.id
    ) {
      hide()
    }
  },
  unlist() {
    hide()
    emit('unlist', props.template)
  },
  approve() {
    return reviewAndRefresh('approve')
  },
  block() {
    hide()
    emit('block', props.template)
  },
  unblock() {
    return reviewAndRefresh('unblock')
  },
  delete() {
    hide()
    emit('delete', props.template)
  },
}

async function reviewAndRefresh(action) {
  const template = props.template
  hide()
  try {
    await decide(template, action)
    emit('changed', template.id)
  } catch (error) {
    notifyIf(error, 'template')
  }
}

function toggle(...args) {
  contextRef.value.toggle(...args)
}

function show(...args) {
  contextRef.value.show(...args)
}

function hide() {
  contextRef.value.hide()
}

function isOpen() {
  return contextRef.value.isOpen()
}

defineExpose({ toggle, show, hide, isOpen })
</script>
