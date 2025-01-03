<template>
  <Dropdown :value="value" fixed-items @input="$emit('input', $event)">
    <DropdownItem
      v-for="fontFamily in googleFontFamilies"
      :key="fontFamily.id"
      :value="fontFamily.id"
      :name="fontFamily.family"
    />
  </Dropdown>
</template>

<script>
import { mapActions } from 'vuex'
import {
  GoogleFontFamilyType
} from '@baserow/modules/builder/fontFamilyTypes'

export default {
  name: 'GoogleFontFamilySelector',
  inject: ['builder'],
  props: {
    value: {
      type: String,
      required: false,
      default: 'Inter',
    },
  },
  computed: {
    googleFontFamilies() {
      return this.$store.getters['theme/getFonts']()

      // Loop over downloaded fonts, then register them.
      // TODO: This should probably happen at page load time
      // const googleFonts = this.$store.getters['theme/getFonts']()
      // for (const font of googleFonts) {
      //   console.log('registered new font: ', font.family)
      //   const name = font.family
      //   const type = font.id
      //   const newGoogleFont = new GoogleFontFamilyType({
      //     app: this.builder,
      //     name,
      //     type,
      //   })
      //   this.$registry.register('fontFamily', newGoogleFont)
      // }
    },
  },
  async mounted() {
    await this.actionFetchFonts()
    this.$store.getters['theme/getFonts']()
  },
  methods: {
    ...mapActions({
      actionFetchFonts: 'theme/fetchFonts',
    }),
  },
}
</script>
