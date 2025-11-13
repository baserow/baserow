<template>
  <SidebarExpandable
    v-if="!isStyle"
    toggle-on-click
    :default-expanded="preventItemNesting ? true : null"
  >
    <template #title>
      <Icon :icon="icon" />
      <span>{{ values.name }}</span>
      <Icon
        v-if="errorMessage"
        :key="errorMessage"
        v-tooltip="errorMessage"
        icon="iconoir-warning-circle"
        size="medium"
        type="error"
      />
    </template>
    <template #default>
      <div v-if="values.type === 'button'">
        <FormGroup
          small-label
          horizontal
          required
          class="margin-bottom-2"
          :label="$t('menuElementForm.menuItemLabelLabel')"
          :error="fieldHasErrors('name')"
        >
          <FormInput
            v-model="v$.values.name.$model"
            :placeholder="$t('menuElementForm.namePlaceholder')"
            :error="fieldHasErrors('name')"
          />
          <template #error>
            {{ v$.values.name.$errors[0]?.$message }}
          </template>
          <template #after-input>
            <ButtonIcon icon="iconoir-bin" @click="removeMenuItem()" />
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
          :error="fieldHasErrors('name')"
        >
          <FormInput
            v-model="v$.values.name.$model"
            :placeholder="$t('menuElementForm.namePlaceholder')"
            :error="fieldHasErrors('name')"
          />
          <template #error>
            {{ v$.values.name.$errors[0]?.$message }}
          </template>
          <template #after-input>
            <ButtonIcon icon="iconoir-bin" @click="removeMenuItem()" />
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
            :value="values.variant"
            :show-search="false"
            @input="values.variant = $event"
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
          v-if="!values.children.length"
          :default-values="defaultValues"
          @values-changed="values = { ...values, ...$event }"
        />
        <div class="menu-element-item-form__children">
          <MenuElementItemForm
            v-for="(child, index) in values.children"
            :key="`${child.uid}-${index}`"
            v-sortable="{
              id: child.uid,
              update: orderChildItems,
              enabled: $hasPermission(
                'builder.page.element.update',
                element,
                workspace.id
              ),
              handle: '[data-sortable-handle]',
            }"
            icon="iconoir-link"
            prevent-item-nesting
            :default-values="child"
            @remove-item="removeChildItem($event)"
            @values-changed="updateChildItem"
          />
        </div>
      </div>
    </template>
    <template v-if="values.type === 'link' && !preventItemNesting" #footer>
      <div class="menu-element-form__add-sub-link-container">
        <ButtonText
          type="primary"
          icon="iconoir-plus"
          size="small"
          @click="addSubLink()"
        >
          {{ $t('menuElementForm.addSubLink') }}
        </ButtonText>
      </div>
    </template>
  </SidebarExpandable>
  <div v-else>
    <div class="menu-element-form__item-wrapper">
      <div
        class="menu-element-form__item-header"
        :class="{
          'menu-element-form__item-header--outline': isStyle,
        }"
        @click.stop="!isStyle ? toggle() : null"
      >
        <div class="menu-element-form__item-handle" data-sortable-handle />
        <div class="menu-element-form__item-title">
          <Icon :icon="icon" />
          <span v-if="values.type === 'separator'">
            {{ $t('menuElement.separator') }}
          </span>
          <span v-else-if="values.type === 'spacer'">
            {{ $t('menuElement.spacer') }}
          </span>
        </div>
        <i
          class="menu-element-form__item-delete iconoir-bin"
          @click="removeMenuItem(values)"
        />
      </div>
    </div>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import elementForm from '@baserow/modules/builder/mixins/elementForm'
import LinkNavigationSelectionForm from '@baserow/modules/builder/components/elements/components/forms/general/LinkNavigationSelectionForm'
import { useVuelidate } from '@vuelidate/core'
import { helpers, required } from '@vuelidate/validators'
import {
  getNextAvailableNameInSequence,
  uuid,
} from '@baserow/modules/core/utils/string'
import { LINK_VARIANTS } from '@baserow/modules/builder/enums'
import SidebarExpandable from '@baserow/modules/builder/components/SidebarExpandable.vue'
import { MenuElementType } from '@baserow/modules/builder/elementTypes'

export default {
  name: 'MenuElementItemForm',
  components: {
    LinkNavigationSelectionForm,
    SidebarExpandable,
  },
  mixins: [elementForm],
  props: {
    /**
     * Controls whether this menu item can nest other menu items. This is
     * allowed by default. Since we only allow one level of nesting for
     * sublinks, this should be false when rendering sublinks.
     */
    preventItemNesting: {
      type: Boolean,
      default: false,
    },
    icon: {
      type: String,
      required: true,
    },
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      values: {
        uid: '',
        name: '',
        type: '',
        variant: '',
        children: [],
        navigation_type: 'page',
        navigate_to_page_id: null,
        navigate_to_url: '',
        page_parameters: [],
        query_parameters: [],
        target: 'self',
      },
      allowedValues: [
        'uid',
        'name',
        'type',
        'variant',
        'children',
        'navigation_type',
        'navigate_to_page_id',
        'navigate_to_url',
        'page_parameters',
        'query_parameters',
        'target',
      ],
    }
  },
  computed: {
    ...mapGetters({
      getElementSelected: 'element/getSelected',
    }),
    isStyle() {
      return ['separator', 'spacer'].includes(this.values.type)
    },
    element() {
      return this.getElementSelected(this.builder)
    },
    menuItemVariants() {
      return [
        {
          label: this.$t('menuElementForm.menuItemVariantLink'),
          value: LINK_VARIANTS.LINK,
        },
        {
          label: this.$t('menuElementForm.menuItemVariantButton'),
          value: LINK_VARIANTS.BUTTON,
        },
      ]
    },
    errorMessage() {
      return this.$registry
        .get('element', MenuElementType.getType())
        .getItemMenuError({
          menuItem: this.values,
          builder: this.builder,
          elementPage: this.elementPage,
          element: this.element,
        })
    },
  },
  methods: {
    /**
     * Responsible for removing this menu item from the `MenuElement` itself.
     */
    removeMenuItem() {
      this.$emit('remove-item', this.values.uid)
    },
    /**
     * Responsible for removing a nested menu item from a parent menu item.
     */
    removeChildItem(uidToRemove) {
      this.values.children = this.values.children.filter(
        (child) => child.uid !== uidToRemove
      )
    },
    /**
     * When a nested meny item is updated, this method is responsible for updating the
     * parent menu item with the new values.
     */
    updateChildItem(newValues) {
      this.values.children = this.values.children.map((item) => {
        if (item.uid === newValues.uid) {
          return { ...item, ...newValues }
        }
        return item
      })
    },
    /**
     * If this menu item is a parent menu item, this method is responsible for
     * adding a child menu item to it.
     */
    addSubLink() {
      const name = getNextAvailableNameInSequence(
        this.$t('menuElementForm.menuItemSubLinkDefaultName'),
        this.values.children.map(({ name }) => name)
      )
      this.values.children.push({
        name,
        variant: LINK_VARIANTS.LINK,
        type: 'link',
        uid: uuid(),
      })
    },
    /**
     * Responsible for sorting the child items of this menu item.
     */
    orderChildItems(newOrder) {
      const itemsByUid = Object.fromEntries(
        this.values.children.map((item) => [item.uid, item])
      )
      this.values.children = newOrder.map((uid) => itemsByUid[uid])
    },
  },
  validations() {
    return {
      values: {
        name: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
      },
    }
  },
}
</script>
