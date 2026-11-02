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
import { computed, ref } from 'vue'
import { useNuxtApp, useRuntimeConfig } from '#app'

import TemplateService from '@baserow/modules/core/services/template'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { getPrivateLinkUrl } from '@baserow/modules/core/utils/userTemplate'
import { copyToClipboard } from '@baserow/modules/core/utils/clipboard'

/**
 * Creates, regenerates or turns off the private link of the author's template.
 */
const props = defineProps({
  // The user's template as listed in their templates, whose
  // `private_link_token` is only shown to them. Null until it's opened.
  template: {
    type: Object,
    required: false,
    default: null,
  },
})

// `changed` is emitted with the template as listed in the user's templates, also
// when the context was closed or opened for another template while the request
// ran.
const emit = defineEmits(['changed', 'shown', 'hidden'])

// The confirmation of each operation. Nothing else shows that a new link
// replaced the old one, of which only the start is shown.
const TOASTS = {
  create: ['createdTitle', 'createdDescription'],
  regenerate: ['regeneratedTitle', 'regeneratedDescription'],
  remove: ['removedTitle', 'removedDescription'],
}

const { $client, $i18n, $router, $store } = useNuxtApp()
const config = useRuntimeConfig()

const contextRef = ref(null)
const copiedRef = ref(null)
// The operation that runs, one at a time.
const operation = ref(null)
const loading = computed(() => operation.value !== null)

const url = computed(() =>
  getPrivateLinkUrl(props.template, $router, config.public.publicWebFrontendUrl)
)

function copy() {
  copyToClipboard(url.value)
  copiedRef.value.show()
}

async function change(newOperation) {
  if (loading.value) {
    return
  }
  operation.value = newOperation
  try {
    const service = TemplateService($client)
    const { slug } = props.template
    const { data } = await (newOperation === 'regenerate'
      ? service.rotatePrivateLinkToken(slug)
      : service.setPrivateLink(slug, newOperation === 'create'))
    emit('changed', data)
    // A link turned off meanwhile, for example in another tab, isn't regenerated.
    if (newOperation !== 'regenerate' || data.private_link_token) {
      const [title, message] = TOASTS[newOperation]
      $store.dispatch('toast/success', {
        title: $i18n.t(`userTemplatePrivateLink.${title}`),
        message: $i18n.t(`userTemplatePrivateLink.${message}`),
      })
    }
  } catch (error) {
    if (error.handler?.code === 'ERROR_TEMPLATE_BLOCKED') {
      error.handler.notifyIf('templates', {
        title: $i18n.t('clientHandler.templateBlockedTitle'),
        message: $i18n.t('userTemplatePrivateLink.blocked'),
      })
      // The owner can no longer manage the link.
      hide()
    } else {
      notifyIf(error, 'templates')
    }
  } finally {
    operation.value = null
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
