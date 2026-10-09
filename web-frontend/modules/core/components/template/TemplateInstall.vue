<template>
  <div class="template-install">
    <Dropdown
      v-if="isAuthenticated"
      v-model="selectedWorkspaceId"
      class="template-install__workspace"
      :placeholder="$t('templateInstall.selectWorkspace')"
      :fixed-items="true"
    >
      <DropdownItem
        v-for="workspaceItem in workspaces"
        :key="workspaceItem.id"
        :name="workspaceItem.name"
        :value="workspaceItem.id"
      ></DropdownItem>
    </Dropdown>
    <div class="template-install__actions">
      <Button
        class="template-install__use"
        full-width
        :loading="installing"
        :disabled="
          installing || (isAuthenticated && selectedWorkspaceId === null)
        "
        @click="use"
        >{{ $t('templateInstall.use') }}</Button
      >
      <ButtonIcon
        ref="moreButton"
        type="secondary"
        icon="iconoir-more-vert"
        :title="$t('templateInstall.more')"
        @click="contextRef.toggle(moreButton.$el, 'top', 'right', 4)"
      ></ButtonIcon>
    </div>
    <Context ref="contextRef">
      <ul class="context__menu">
        <li class="context__menu-item">
          <a class="context__menu-item-link" @click.prevent="copyLink">
            <i class="context__menu-item-icon iconoir-link"></i>
            {{ $t('templateInstall.copyLink') }}
            <Copied ref="copiedRef"></Copied>
          </a>
        </li>
      </ul>
    </Context>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useStore } from 'vuex'
import { useNuxtApp, useRouter, useRuntimeConfig } from '#app'

import { notifyIf } from '@baserow/modules/core/utils/error'
import TemplateService from '@baserow/modules/core/services/template'

const props = defineProps({
  template: {
    type: Object,
    required: true,
  },
  // The workspace the template is installed into by default. When null, the
  // selected or else the first workspace is used.
  workspace: {
    type: Object,
    required: false,
    default: null,
  },
})

const emit = defineEmits(['installed'])

const store = useStore()
const router = useRouter()
const config = useRuntimeConfig()
const { $client } = useNuxtApp()

const moreButton = ref(null)
const contextRef = ref(null)
const copiedRef = ref(null)
const job = ref(null)
const installing = ref(false)

const isAuthenticated = computed(() => store.getters['auth/isAuthenticated'])

// Deliberately not filtered by the `workspace.create_application` permission
// because the granular permissions are only fetched for the selected workspace,
// and fetching them for all workspaces is too expensive. The backend rejects the
// install if the user doesn't have permission.
const workspaces = computed(() => store.getters['workspace/getAllSorted'])

const selectedWorkspaceId = ref(
  props.workspace?.id ??
    store.getters['workspace/getSelected']?.id ??
    workspaces.value[0]?.id ??
    null
)

watch(
  () => job.value?.state,
  (state) => {
    if (['finished', 'failed'].includes(state)) {
      installing.value = false
    }
  }
)

async function use() {
  if (!isAuthenticated.value) {
    // The template page can show another template than the one in its URL, so
    // the user is sent back to this template's own page after logging in.
    const original = templateRoute().fullPath
    await router.push({ name: 'login', query: { original } })
    return
  }

  installing.value = true
  const workspaceId = selectedWorkspaceId.value

  try {
    const { data } = await TemplateService($client).asyncInstall(
      workspaceId,
      props.template.id
    )
    job.value = data
    store.dispatch('job/create', data)
    emit('installed')

    // If the template is installed into another workspace than the one the user
    // is looking at, redirect to its homepage where they can see the template
    // being installed.
    if (props.workspace?.id !== workspaceId) {
      await router.push({ name: 'workspace', params: { workspaceId } })
    }
  } catch (error) {
    notifyIf(error, 'template')
    installing.value = false
  }
}

function templateRoute() {
  return router.resolve({
    name: 'template',
    params: { slug: props.template.slug },
  })
}

async function copyLink() {
  const { href } = templateRoute()
  await navigator.clipboard.writeText(
    new URL(href, config.public.publicWebFrontendUrl).toString()
  )
  copiedRef.value.show()
}
</script>
