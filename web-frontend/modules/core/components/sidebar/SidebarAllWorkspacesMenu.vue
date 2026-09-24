<template>
  <div class="sidebar__section" ph-autocapture="sidebar">
    <ul class="tree">
      <nuxt-link
        v-slot="{ href, navigate, isExactActive }"
        custom
        :to="{ name: 'all-workspaces' }"
      >
        <li
          class="tree__item"
          :class="{
            active: isExactActive,
          }"
        >
          <div class="tree__action sidebar__action">
            <a :href="href" class="tree__link" @click="navigate">
              <i class="tree__icon iconoir-home-simple"></i>
              <span class="tree__link-text">
                <span class="sidebar__item-name">{{
                  $t('sidebar.allWorkspaces')
                }}</span>
              </span>
            </a>
          </div>
        </li>
      </nuxt-link>

      <li class="tree__item">
        <div class="tree__action sidebar__action">
          <a class="tree__link" @click="$refs.templateModal.show()">
            <i class="tree__icon iconoir-page"></i>
            <span class="tree__link-text">
              <span class="sidebar__item-name">{{
                $t('sidebar.templates')
              }}</span>
            </span>
          </a>
          <TemplateModal ref="templateModal"></TemplateModal>
        </div>
      </li>

      <li class="tree__item">
        <div class="tree__action sidebar__action">
          <a class="tree__link" @click="$refs.trashModal.show()">
            <i class="tree__icon iconoir-bin"></i>
            <span class="tree__link-text">
              <span class="sidebar__item-name">{{ $t('sidebar.trash') }}</span>
            </span>
          </a>
          <TrashModal ref="trashModal"></TrashModal>
        </div>
      </li>
    </ul>
  </div>
</template>

<script>
import TrashModal from '@baserow/modules/core/components/trash/TrashModal'
import TemplateModal from '@baserow/modules/core/components/template/TemplateModal'

export default {
  name: 'SidebarAllWorkspacesMenu',
  components: {
    TrashModal,
    TemplateModal,
  },
}
</script>
