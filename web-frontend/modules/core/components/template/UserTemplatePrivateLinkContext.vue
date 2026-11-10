<template>
  <Context
    ref="contextRef"
    class="user-template-private-link"
    max-height-if-outside-viewport
    @shown="emit('shown')"
    @hidden="emit('hidden')"
  >
    <template v-if="template">
      <div v-if="!url" class="user-template-private-link__empty">
        <div class="user-template-private-link__empty-title">
          {{ $t('userTemplatePrivateLink.emptyTitle') }}
        </div>
        <p class="user-template-private-link__description">
          {{ $t('userTemplatePrivateLink.emptyDescription') }}
        </p>
        <Button
          type="secondary"
          icon="iconoir-link"
          :loading="loading"
          :disabled="loading"
          @click="change('create')"
        >
          {{ $t('userTemplatePrivateLink.create') }}
        </Button>
      </div>
      <template v-else>
        <div class="user-template-private-link__shared">
          <div class="user-template-private-link__title">
            {{ $t('userTemplatePrivateLink.sharedTitle') }}
          </div>
          <p class="user-template-private-link__description">
            {{ $t('userTemplatePrivateLink.sharedDescription') }}
          </p>
          <div class="user-template-private-link__url">
            <div class="user-template-private-link__url-box">{{ url }}</div>
            <button
              v-tooltip="$t('userTemplatePrivateLink.copy')"
              :aria-label="$t('userTemplatePrivateLink.copy')"
              type="button"
              class="user-template-private-link__action"
              @click="copy"
            >
              <i class="iconoir-copy"></i>
              <Copied ref="copiedRef"></Copied>
            </button>
            <button
              v-tooltip="$t('userTemplatePrivateLink.regenerate')"
              :aria-label="$t('userTemplatePrivateLink.regenerate')"
              type="button"
              class="user-template-private-link__action"
              :class="{
                'user-template-private-link__action--loading':
                  operation === 'regenerate',
              }"
              :disabled="loading"
              @click="change('regenerate')"
            >
              <i class="iconoir-refresh"></i>
            </button>
          </div>
          <div class="user-template-private-link__hint">
            {{ $t('userTemplatePrivateLink.regenerateHint') }}
          </div>
        </div>
        <div class="context__footer">
          <ButtonText
            icon="iconoir-cancel"
            :loading="operation === 'remove'"
            :disabled="loading"
            @click="change('remove')"
          >
            {{ $t('userTemplatePrivateLink.remove') }}
          </ButtonText>
        </div>
      </template>
    </template>
  </Context>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useNuxtApp, useRuntimeConfig } from '#app'

import TemplateService from '@baserow/modules/core/services/template'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { getPrivateLinkUrl } from '@baserow/modules/core/utils/userTemplate'
import { copyToClipboard } from '@baserow/modules/core/utils/clipboard'

const props = defineProps({
  template: {
    type: Object,
    required: false,
    default: null,
  },
})

const emit = defineEmits(['changed', 'shown', 'hidden'])

const TOASTS = {
  create: [
    'userTemplatePrivateLink.createdTitle',
    'userTemplatePrivateLink.createdDescription',
  ],
  regenerate: [
    'userTemplatePrivateLink.regeneratedTitle',
    'userTemplatePrivateLink.regeneratedDescription',
  ],
  remove: [
    'userTemplatePrivateLink.removedTitle',
    'userTemplatePrivateLink.removedDescription',
  ],
}

const { $client, $i18n, $router, $store } = useNuxtApp()
const config = useRuntimeConfig()

const contextRef = ref(null)
const copiedRef = ref(null)
const operations = ref(new Map())
const operation = computed(
  () => operations.value.get(props.template?.id) ?? null
)
const loading = computed(() => operation.value !== null)

const url = computed(() =>
  getPrivateLinkUrl(props.template, $router, config.public.publicWebFrontendUrl)
)

watch(
  () => props.template?.state,
  (state) => {
    if (state === 'blocked') {
      hide()
    }
  }
)

async function copy() {
  try {
    await copyToClipboard(url.value)
  } catch {
    $store.dispatch('toast/error', { title: $i18n.t('copied.linkFailed') })
    return
  }
  copiedRef.value?.show()
}

async function change(newOperation) {
  if (loading.value) {
    return
  }
  const { id, slug } = props.template
  operations.value.set(id, newOperation)
  try {
    const service = TemplateService($client)
    const { data } = await (newOperation === 'regenerate'
      ? service.rotatePrivateLinkToken(slug)
      : service.setPrivateLink(slug, newOperation === 'create'))
    emit('changed', data)
    if (newOperation !== 'regenerate' || data.private_link_token) {
      const [title, message] = TOASTS[newOperation]
      $store.dispatch('toast/success', {
        title: $i18n.t(title),
        message: $i18n.t(message),
      })
    }
  } catch (error) {
    if (error.handler?.code === 'ERROR_TEMPLATE_BLOCKED') {
      error.handler.notifyIf('templates', {
        title: $i18n.t('clientHandler.templateBlockedTitle'),
        message: $i18n.t('userTemplatePrivateLink.blocked'),
      })
      if (props.template?.id === id) {
        hide()
      }
    } else {
      notifyIf(error, 'templates')
    }
  } finally {
    operations.value.delete(id)
  }
}

function toggle(...args) {
  contextRef.value.toggle(...args)
}

function hide() {
  contextRef.value.hide()
}

function isOpen() {
  return contextRef.value.isOpen()
}

defineExpose({ toggle, hide, isOpen })
</script>
