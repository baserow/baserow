export const getCardHeight = (fields, coverImageField, registry) => {
  // margin-bottom of card.scss.card__field, that we don't have to compensate for
  // if there aren't any fields in the card.
  const fieldMarginBottom = fields.length === 0 ? 0 : 10

  return (
    // Some of these values must be kep in sync with card.scss
    fields.reduce((accumulator, field) => {
      const fieldType = registry.get('field', field._.type.type)
      return (
        accumulator +
        fieldType.getCardValueHeight(field) +
        6 + // margin-bottom of card.scss.card__field-name
        18 + // line-height of card.scss.card__field-name
        10 // margin-bottom of card.scss.card__field
      )
    }, 0) +
    (coverImageField === null ? 0 : 160) + // height of card.scss.card__cover
    16 + // padding-top of card.scss.card
    16 - // padding-bottom of card.scss.card
    fieldMarginBottom +
    2 // border of card.scss.card
  )
}
