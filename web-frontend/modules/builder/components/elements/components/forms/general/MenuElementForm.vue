<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      :label="$t('repeatElementForm.orientationLabel')"
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

    <div
      ref="menuItemAddContainer"
      class="menu-element__form--add-item-container"
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

    <Context ref="menuItemAddContext" :hide-on-click-outside="true">
      <div class="menu-element__form--add-item-context">
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

    <div v-for="item in values.menu_items" :key="item.uid">
      <Expandable
        v-if="item.parent_menu_item === null"
        v-sortable="{
          id: item.uid,
          update: orderMenuItems,
          enabled: $hasPermission(
            'builder.page.element.update',
            element,
            workspace.id
          ),
          handle: '[data-sortable-handle]',
        }"
      >
        <template #header="{ toggle, expanded }">
          <div
            :class="
              menuItemTypeIsStyle(item.type)
                ? 'menu-element__form--expandable-item-header-outline'
                : 'menu-element__form--expandable-item-header'
            "
            @click.stop="!menuItemTypeIsStyle(item.type) ? toggle() : null"
          >
            <div
              class="menu-element__form--expandable-item-handle"
              data-sortable-handle
            />
            <div class="menu-element__form--expandable-item-name">
              <i
                v-if="!expanded && menuItemInError(item)"
                class="menu-element__form--expandable-item-error iconoir-warning-circle"
              ></i>
              <template v-if="item.type === 'separator'">
                {{ $t('menuElement.separator') }}
              </template>
              <template v-else-if="item.type === 'spacer'">
                {{ $t('menuElement.spacer') }}
              </template>
              <template v-else>
                {{ item.name }}
              </template>
            </div>

            <template v-if="menuItemTypeIsStyle(item.type)">
              <ButtonIcon
                size="small"
                icon="iconoir-bin"
                @click="removeMenuItem(item)"
              />
            </template>
            <template v-else>
              <i
                :class="
                  expanded
                    ? 'iconoir-nav-arrow-down'
                    : 'iconoir-nav-arrow-right'
                "
              />
            </template>
          </div>
        </template>
        <template v-if="!menuItemTypeIsStyle(item.type)" #default>
          <div class="menu-element__form--expanded-item">
            <div v-if="item.type === 'button'">
              <FormGroup
                small-label
                horizontal
                required
                class="margin-bottom-2"
                :label="$t('menuElementForm.menuItemLabelLabel')"
              >
                <FormInput
                  v-model="item.name"
                  :placeholder="$t('menuElementForm.namePlaceholder')"
                />
                <template #after-input>
                  <ButtonIcon
                    icon="iconoir-bin"
                    @click="removeMenuItem(item)"
                  />
                </template>
              </FormGroup>
              <Alert type="info-neutral">
                <p>{{ $t('menuElementForm.eventDescription') }}</p>
              </Alert>
            </div>
            <div v-else>
              <FormGroup
                small-label
                horizontal
                required
                class="margin-bottom-2"
                :label="$t('menuElementForm.menuItemLabelLabel')"
              >
                <FormInput
                  v-model="item.name"
                  :placeholder="$t('menuElementForm.namePlaceholder')"
                />
                <template #after-input>
                  <ButtonIcon
                    icon="iconoir-bin"
                    @click="removeMenuItem(item)"
                  />
                </template>
              </FormGroup>
              <FormGroup
                small-label
                horizontal
                required
                :label="$t('menuElementForm.menuItemVariantLabel')"
                class="margin-bottom-2"
              >
                <Dropdown
                  :value="item.variant"
                  :show-search="false"
                  @input="changeItemVariant(item, $event)"
                >
                  <DropdownItem
                    v-for="itemVariant in menuItemVariants"
                    :key="itemVariant.value"
                    :name="itemVariant.label"
                    :value="itemVariant.value"
                  />
                </Dropdown>
              </FormGroup>

              <LinkNavigationSelectionForm
                v-if="!item.children?.length"
                :default-values="item"
                @values-changed="updateItem(item, $event)"
              />

              <div v-if="item.children?.length">
                <div v-for="child in item.children" :key="child.uid">
                  <Expandable>
                    <template #header="{ toggle, expanded }">
                      <div
                        class="menu-element__form--expandable-item-header"
                        @click.stop="toggle"
                      >
                        <div
                          class="menu-element__form--expandable-item-handle"
                          data-sortable-handle
                        />
                        <div class="menu-element__form--expandable-item-name">
                          <i
                            v-if="!expanded && menuItemInError(child)"
                            class="menu-element__form--expandable-item-error iconoir-warning-circle"
                          ></i>
                          {{ child.name }}
                        </div>
                        <i
                          :class="
                            expanded
                              ? 'iconoir-nav-arrow-down'
                              : 'iconoir-nav-arrow-right'
                          "
                        />
                      </div>
                    </template>

                    <template #default>
                      <div class="menu-element__form--expanded-item">
                        <FormGroup
                          small-label
                          horizontal
                          required
                          class="margin-bottom-2"
                          :label="$t('menuElementForm.menuItemLabelLabel')"
                        >
                          <FormInput
                            v-model="child.name"
                            :placeholder="$t('menuElementForm.namePlaceholder')"
                          />
                          <template #after-input>
                            <ButtonIcon
                              icon="iconoir-bin"
                              @click="removeChildItem(item, child)"
                            />
                          </template>
                        </FormGroup>

                        <FormGroup
                          small-label
                          horizontal
                          required
                          :label="$t('menuElementForm.menuItemVariantLabel')"
                          class="margin-bottom-2"
                        >
                          <Dropdown
                            :value="child.variant"
                            :show-search="false"
                            @input="changeSubLinkVariant(child, $event)"
                          >
                            <DropdownItem
                              v-for="itemVariant in menuItemVariants"
                              :key="itemVariant.value"
                              :name="itemVariant.label"
                              :value="itemVariant.value"
                            />
                          </Dropdown>
                        </FormGroup>

                        <LinkNavigationSelectionForm
                          :default-values="child"
                          @values-changed="updateSubLink(child, $event)"
                        />
                      </div>
                    </template>
                  </Expandable>
                </div>
              </div>

              <div class="menu-element__add-sub-link-container">
                <ButtonText
                  type="primary"
                  icon="iconoir-plus"
                  size="small"
                  @click="addSubLink(item)"
                >
                  {{ $t('menuElementForm.addSubLink') }}
                </ButtonText>
              </div>
            </div>
          </div>
        </template>
      </Expandable>
    </div>
  </form>
</template>

<script>
import elementForm from '@baserow/modules/builder/mixins/elementForm'
import { MENU_ORIENTATION } from '@baserow/modules/builder/enums'
import {
  getNextAvailableNameInSequence,
  uuid,
} from '@baserow/modules/core/utils/string'
import LinkNavigationSelectionForm from '@baserow/modules/builder/components/elements/components/forms/general/LinkNavigationSelectionForm'
import { mapGetters } from 'vuex'

export default {
  name: 'MenuElementForm',
  components: {
    LinkNavigationSelectionForm,
  },
  mixins: [elementForm],
  data() {
    return {
      values: {
        value: '',
        styles: {},
        orientation: 'vertical',
        menu_items: [],
      },
      allowedValues: ['value', 'styles', 'menu_items', 'orientation'],
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
        // {
        //   icon: 'baserow-icon-spacer',
        //   label: this.$t('menuElementForm.menuItemAddSpacer'),
        //   type: 'spacer',
        // },
      ],
    }
  },
  computed: {
    ...mapGetters({
      getElementSelected: 'element/getSelected',
    }),
    MENU_ORIENTATION() {
      return MENU_ORIENTATION
    },
    menuItemTypes() {
      return [
        {
          label: this.$t('menuElementForm.menuItemTypeItem'),
          value: 'item',
        },
        {
          label: this.$t('menuElementForm.menuItemTypeSeparator'),
          value: 'separator',
        },
      ]
    },
    menuItemVariants() {
      return [
        {
          label: this.$t('menuElementForm.menuItemVariantLink'),
          value: 'link',
        },
        {
          label: this.$t('menuElementForm.menuItemVariantButton'),
          value: 'button',
        },
      ]
    },
    element() {
      return this.getElementSelected(this.builder)
    },
    orientationOptions() {
      return [
        {
          label: this.$t('menuElementForm.orientationVertical'),
          value: 'vertical',
          icon: 'iconoir-table-rows',
        },
        {
          label: this.$t('repeatElementForm.orientationHorizontal'),
          value: 'horizontal',
          icon: 'iconoir-view-columns-3',
        },
      ]
    },
  },
  methods: {
    addMenuItem(type) {
      const name = getNextAvailableNameInSequence(
        this.$t('menuElementForm.menuItemDefaultName'),
        this.values.menu_items
          .filter((item) => item.parent_menu_item === null)
          .map(({ name }) => name)
      )

      this.values.menu_items.push({
        name,
        variant: 'link',
        value: '',
        type,
        parent_menu_item: null,
        uid: uuid(),
        children: [],
      })

      this.$refs.menuItemAddContext.hide()
    },
    menuItemTypeIsStyle(itemType) {
      return ['separator', 'spacer'].includes(itemType)
    },
    changeItemVariant(itemToUpdate, newVariant) {
      this.updateItem(itemToUpdate, { variant: newVariant })
    },
    changeSubLinkVariant(itemToUpdate, newVariant) {
      this.updateSubLink(itemToUpdate, { variant: newVariant })
    },
    orderMenuItems(newOrder) {
      // TODO
    },
    menuItemInError(item) {
      // TODO
      return false
    },
    removeMenuItem(menuItem) {
      this.values.menu_items = this.values.menu_items.filter(
        (item) => item !== menuItem
      )
    },
    removeChildItem(parent, child) {
      this.values.menu_items = this.values.menu_items.map((item) => {
        if (item.uid === parent.uid) {
          return {
            ...item,
            children: item.children.filter((c) => c.uid !== child.uid),
          }
        }
        return item
      })
    },
    updateItem(menuItem, values) {
      this.values.menu_items = this.values.menu_items.map((item) => {
        if (item.uid === menuItem.uid) {
          return { ...item, ...values }
        }
        return item
      })
    },
    updateSubLink(child, values) {
      this.values.menu_items = this.values.menu_items.map((item) => {
        if (item.children) {
          return {
            ...item,
            children: item.children.map((subItem) =>
              subItem.uid === child.uid ? { ...subItem, ...values } : subItem
            ),
          }
        }
        return item
      })
    },
    addSubLink(item) {
      const name = getNextAvailableNameInSequence(
        this.$t('menuElementForm.menuItemSubLinkDefaultName'),
        item.children.map(({ name }) => name)
      )
      const subItem = {
        name,
        variant: 'link',
        type: 'link',
        uid: uuid(),
      }

      if (!Array.isArray(item.children)) {
        this.$set(item, 'children', [subItem])
      } else {
        this.$set(item.children, item.children.length, subItem)
      }
    },
  },
}
</script>
