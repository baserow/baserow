<template>
  <form @submit.prevent @keydown.enter.prevent>
    <CustomStyleButton
      v-model="values.styles"
      style-key="menu"
      :config-block-types="['button', 'link']"
      :theme="builder.theme"
      :extra-args="{ noAlignment: true, noWidth: true, onlyBody: true }"
    />
    <FormGroup
      :label="$t('orientations.label')"
      small-label
      required
      class="margin-bottom-2"
    >
      <RadioGroup
        v-model="values.orientation"
        :options="orientationOptions"
        type="button"
      >
      </RadioGroup>
    </FormGroup>

    <FormGroup
      v-if="values.orientation === ORIENTATIONS.HORIZONTAL"
      :label="$t('menuElementForm.alignment')"
      small-label
      required
      class="margin-bottom-2"
    >
      <HorizontalAlignmentsSelector v-model="values.alignment" />
    </FormGroup>

    <CustomStyleButton
      v-model="values.styles"
      style-key="burger"
      :config-block-types="['typography']"
      :theme="builder.theme"
      :extra-args="{
        onlyBody: true,
        noAlignment: true,
        noFontSelector: true,
        noFontWeight: true,
      }"
    />
    <FormGroup
      :label="$t('menuElementForm.variant')"
      small-label
      required
      class="margin-bottom-2"
    >
      <DeviceSelector
        :device-type-selected="deviceTypeSelected"
        direction="row"
        @selected="actionSetDeviceTypeSelected"
      >
        <template #deviceTypeControl="{ deviceType }">
          <RadioButton
            v-for="variant in menuVariants"
            :key="variant.value"
            v-model="values.variant[deviceType.getType()]"
            :icon="variant.icon"
            :value="variant.value"
          >
            {{ variant.label }}
          </RadioButton>
        </template>
      </DeviceSelector>
    </FormGroup>
    <FormGroup
      v-if="isCompactMenuSelected"
      small-label
      required
      class="margin-bottom-2"
      :label="$t('menuElementForm.previewCompactMenuLabel')"
      :helper-text="$t('menuElementForm.previewCompactMenuHelper')"
    >
      <Button
        :icon="editorCompactMenuToggleIcon"
        size="small"
        @click="toggleEditorCompactMenu"
      >
        {{ editorCompactMenuToggleLabel }}
      </Button>
    </FormGroup>

    <div
      ref="menuItemAddContainer"
      class="menu-element-form__add-item-container"
    >
      <div>
        {{ $t('menuElementForm.menuItemsLabel') }}
      </div>
      <div>
        <ButtonText
          type="primary"
          icon="iconoir-plus"
          size="small"
          @click="
            $refs.menuItemAddContext.show(
              $refs.menuItemAddContainer,
              'bottom',
              'right'
            )
          "
        >
          {{ $t('menuElementForm.addMenuItemLink') }}
        </ButtonText>
      </div>
    </div>
    <p v-if="!values.menu_items.length">
      {{ $t('menuElementForm.noMenuItemsMessage') }}
    </p>
    <Context ref="menuItemAddContext" :hide-on-click-outside="true">
      <div class="menu-element-form__add-item-context">
        <ButtonText
          v-for="(menuItemType, index) in addMenuItemTypes"
          :key="index"
          type="primary"
          :icon="menuItemType.icon"
          size="small"
          @click="addMenuItem(menuItemType.type)"
        >
          {{ menuItemType.label }}
        </ButtonText>
      </div>
    </Context>
    <div class="menu-element-form__items">
      <MenuElementItemForm
        v-for="(item, index) in values.menu_items"
        :key="`${item.uid}-${index}`"
        v-sortable="{
          id: item.uid,
          update: orderRootItems,
          enabled: $hasPermission(
            'builder.page.element.update',
            element,
            workspace.id
          ),
          handle: '[data-sortable-handle]',
        }"
        :icon="getIcon(item.type)"
        :default-values="item"
        @remove-item="removeMenuItem($event)"
        @values-changed="updateMenuItem"
      />
    </div>
  </form>
</template>

<script>
import elementForm from '@baserow/modules/builder/mixins/elementForm'
import {
  HORIZONTAL_ALIGNMENTS,
  ORIENTATIONS,
} from '@baserow/modules/builder/enums'
import DeviceSelector from '@baserow/modules/builder/components/page/header/DeviceSelector.vue'
import {
  getNextAvailableNameInSequence,
  uuid,
} from '@baserow/modules/core/utils/string'
import { mapGetters, mapActions } from 'vuex'
import MenuElementItemForm from '@baserow/modules/builder/components/elements/components/forms/general/MenuElementItemForm'
import CustomStyleButton from '@baserow/modules/builder/components/elements/components/forms/style/CustomStyleButton'
import HorizontalAlignmentsSelector from '@baserow/modules/builder/components/HorizontalAlignmentsSelector'

export default {
  name: 'MenuElementForm',
  components: {
    MenuElementItemForm,
    CustomStyleButton,
    HorizontalAlignmentsSelector,
    DeviceSelector,
  },
  mixins: [elementForm],
  data() {
    return {
      values: {
        value: '',
        styles: {},
        orientation: ORIENTATIONS.VERTICAL,
        alignment: HORIZONTAL_ALIGNMENTS.LEFT,
        menu_items: [],
        variant: {},
      },
      allowedValues: [
        'value',
        'styles',
        'menu_items',
        'orientation',
        'alignment',
        'variant',
      ],
      menuVariants: [
        {
          icon: 'iconoir-enlarge-round-arrow',
          label: this.$t('menuElementForm.expanded'),
          value: 'expanded',
        },
        {
          icon: 'iconoir-menu',
          label: this.$t('menuElementForm.compact'),
          value: 'compact',
        },
      ],
      addMenuItemTypes: [
        {
          icon: 'iconoir-link',
          label: this.$t('menuElementForm.menuItemAddLink'),
          type: 'link',
        },
        {
          icon: 'iconoir-cursor-pointer',
          label: this.$t('menuElementForm.menuItemAddButton'),
          type: 'button',
        },
        {
          icon: 'baserow-icon-separator',
          label: this.$t('menuElementForm.menuItemAddSeparator'),
          type: 'separator',
        },
        {
          icon: 'baserow-icon-spacer',
          label: this.$t('menuElementForm.menuItemAddSpacer'),
          type: 'spacer',
        },
      ],
    }
  },
  computed: {
    ...mapGetters({
      getElementSelected: 'element/getSelected',
      deviceTypeSelected: 'page/getDeviceTypeSelected',
    }),
    ORIENTATIONS() {
      return ORIENTATIONS
    },
    element() {
      return this.getElementSelected(this.builder)
    },
    editorCompactMenuOpen() {
      return this.element._.compactMenuOpen
    },
    isCompactMenuSelected() {
      return this.values.variant?.[this.deviceTypeSelected] === 'compact'
    },
    editorCompactMenuToggleIcon() {
      return this.editorCompactMenuOpen ? 'iconoir-cancel' : 'iconoir-menu'
    },
    editorCompactMenuToggleLabel() {
      return this.editorCompactMenuOpen
        ? this.$t('menuElementForm.closeEditorCompactMenu')
        : this.$t('menuElementForm.openEditorCompactMenu')
    },
    orientationOptions() {
      return [
        {
          label: this.$t('orientations.vertical'),
          value: ORIENTATIONS.VERTICAL,
          icon: 'iconoir-table-rows',
        },
        {
          label: this.$t('orientations.horizontal'),
          value: ORIENTATIONS.HORIZONTAL,
          icon: 'iconoir-view-columns-3',
        },
      ]
    },
  },
  methods: {
    getIcon(itemType) {
      return this.addMenuItemTypes.find(({ type }) => type === itemType).icon
    },
    ...mapActions({
      actionSetDeviceTypeSelected: 'page/setDeviceTypeSelected',
      actionForceUpdateElement: 'element/forceUpdate',
    }),
    toggleEditorCompactMenu() {
      this.actionForceUpdateElement({
        builder: this.builder,
        page: this.elementPage,
        element: this.element,
        values: {
          _: {
            ...this.element._,
            compactMenuOpen: !this.element._.compactMenuOpen,
          },
        },
      })
    },
    addMenuItem(type) {
      const name = getNextAvailableNameInSequence(
        this.$t('menuElementForm.menuItemDefaultName'),
        this.values.menu_items
          .filter((item) => item.parent_menu_item === null)
          .map(({ name }) => name)
      )

      this.values.menu_items = [
        ...this.values.menu_items,
        {
          name,
          variant: 'link',
          value: '',
          type,
          uid: uuid(),
          children: [],
          parent_menu_item: null, // This is the root menu item.
        },
      ]
      this.$refs.menuItemAddContext.hide()
    },
    /**
     * When a menu item is removed, this method is responsible for removing it
     * from the `MenuElement` itself.
     */
    removeMenuItem(uidToRemove) {
      this.values.menu_items = this.values.menu_items.filter(
        (item) => item.uid !== uidToRemove
      )
    },
    /**
     * When a menu item is updated, this method is responsible for updating the
     * `MenuElement` with the new values.
     */
    updateMenuItem(newValues) {
      this.values.menu_items = this.values.menu_items.map((item) => {
        if (item.uid === newValues.uid) {
          return { ...item, ...newValues }
        }
        return item
      })
    },
    /**
     * Responsible for sorting the root items of this menu item.
     */
    orderRootItems(newOrder) {
      const itemsByUid = Object.fromEntries(
        this.values.menu_items.map((item) => [item.uid, item])
      )
      this.values.menu_items = newOrder.map((uid) => itemsByUid[uid])
    },
  },
}
</script>
