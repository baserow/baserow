import importer from '@baserow/modules/database/mixins/importer'

describe('test file importer', () => {
  test('field name id is invalid as is reserved by baserow', () => {
    expect(importer.methods.makeHeaderUniqueAndValid(['id'])).toEqual(['id 2'])
    expect(importer.methods.makeHeaderUniqueAndValid(['id', 'id 2'])).toEqual([
      'id 3',
      'id 2',
    ])
  })
  test('field name order is invalid as is reserved by baserow', () => {
    expect(importer.methods.makeHeaderUniqueAndValid(['order'])).toEqual([
      'order 2',
    ])
    expect(
      importer.methods.makeHeaderUniqueAndValid(['order', 'order 2', 'order'])
    ).toEqual(['order 3', 'order 2', 'order 4'])
  })
  test('duplicate names are appended with numbers to make them unique', () => {
    expect(importer.methods.makeHeaderUniqueAndValid(['a', 'a', 'a'])).toEqual([
      'a',
      'a 2',
      'a 3',
    ])
    expect(
      importer.methods.makeHeaderUniqueAndValid(['a', 'a 2', 'a', 'a'])
    ).toEqual(['a', 'a 2', 'a 3', 'a 4'])
  })
  test('blank names are replaced by unique field names', () => {
    expect(importer.methods.makeHeaderUniqueAndValid(['', '', ''])).toEqual([
      'Field 1',
      'Field 2',
      'Field 3',
    ])
    expect(
      importer.methods.makeHeaderUniqueAndValid(['', 'Field 1', '', ''])
    ).toEqual(['Field 2', 'Field 1', 'Field 3', 'Field 4'])
  })
  test('too long names get truncated to max length', () => {
    const header = ['x'.repeat(255), 'y'.repeat(256), 'z'.repeat(300)]
    const expectedHeader = ['x'.repeat(255), 'y'.repeat(255), 'z'.repeat(255)]
    expect(importer.methods.makeHeaderUniqueAndValid(header)).toEqual(
      expectedHeader
    )
  })
  test('too long names with duplicates get truncated to max length', () => {
    // header with field names of 260char length
    const header = [
      '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',
    ]

    const expectedHeader = [
      'bvXP1mSFkVIGfxlJZZ5ERYojgjeOVxV8K7wHuGUrusrpaRJL2gHFyad6GicYmFgFNJlibN8CcxLd1j2kireT6VxIgeN63Rr1G7vPQr9DfmUqDjDTGs8ka8gSpKsoYaUcd1FGEcmNx1B2r3w9SG0K56MmoBZklx2LmDcSJ4PL7y8gSdvYCWNuhDxcjQT3mUIVFyNrIMZ4mTCH98JH9CouOkb0KEgnZ34K8U42HWEZFLQFZ8v6ec9GixED27bHgxy',
      'bvXP1mSFkVIGfxlJZZ5ERYojgjeOVxV8K7wHuGUrusrpaRJL2gHFyad6GicYmFgFNJlibN8CcxLd1j2kireT6VxIgeN63Rr1G7vPQr9DfmUqDjDTGs8ka8gSpKsoYaUcd1FGEcmNx1B2r3w9SG0K56MmoBZklx2LmDcSJ4PL7y8gSdvYCWNuhDxcjQT3mUIVFyNrIMZ4mTCH98JH9CouOkb0KEgnZ34K8U42HWEZFLQFZ8v6ec9GixED27bHg 2',
      'bvXP1mSFkVIGfxlJZZ5ERYojgjeOVxV8K7wHuGUrusrpaRJL2gHFyad6GicYmFgFNJlibN8CcxLd1j2kireT6VxIgeN63Rr1G7vPQr9DfmUqDjDTGs8ka8gSpKsoYaUcd1FGEcmNx1B2r3w9SG0K56MmoBZklx2LmDcSJ4PL7y8gSdvYCWNuhDxcjQT3mUIVFyNrIMZ4mTCH98JH9CouOkb0KEgnZ34K8U42HWEZFLQFZ8v6ec9GixED27bHg 3',
      'bvXP1mSFkVIGfxlJZZ5ERYojgjeOVxV8K7wHuGUrusrpaRJL2gHFyad6GicYmFgFNJlibN8CcxLd1j2kireT6VxIgeN63Rr1G7vPQr9DfmUqDjDTGs8ka8gSpKsoYaUcd1FGEcmNx1B2r3w9SG0K56MmoBZklx2LmDcSJ4PL7y8gSdvYCWNuhDxcjQT3mUIVFyNrIMZ4mTCH98JH9CouOkb0KEgnZ34K8U42HWEZFLQFZ8v6ec9GixED27bHg 4',
      'bvXP1mSFkVIGfxlJZZ5ERYojgjeOVxV8K7wHuGUrusrpaRJL2gHFyad6GicYmFgFNJlibN8CcxLd1j2kireT6VxIgeN63Rr1G7vPQr9DfmUqDjDTGs8ka8gSpKsoYaUcd1FGEcmNx1B2r3w9SG0K56MmoBZklx2LmDcSJ4PL7y8gSdvYCWNuhDxcjQT3mUIVFyNrIMZ4mTCH98JH9CouOkb0KEgnZ34K8U42HWEZFLQFZ8v6ec9GixED27bHg 5',
      'bvXP1mSFkVIGfxlJZZ5ERYojgjeOVxV8K7wHuGUrusrpaRJL2gHFyad6GicYmFgFNJlibN8CcxLd1j2kireT6VxIgeN63Rr1G7vPQr9DfmUqDjDTGs8ka8gSpKsoYaUcd1FGEcmNx1B2r3w9SG0K56MmoBZklx2LmDcSJ4PL7y8gSdvYCWNuhDxcjQT3mUIVFyNrIMZ4mTCH98JH9CouOkb0KEgnZ34K8U42HWEZFLQFZ8v6ec9GixED27bHg 6',
      'bvXP1mSFkVIGfxlJZZ5ERYojgjeOVxV8K7wHuGUrusrpaRJL2gHFyad6GicYmFgFNJlibN8CcxLd1j2kireT6VxIgeN63Rr1G7vPQr9DfmUqDjDTGs8ka8gSpKsoYaUcd1FGEcmNx1B2r3w9SG0K56MmoBZklx2LmDcSJ4PL7y8gSdvYCWNuhDxcjQT3mUIVFyNrIMZ4mTCH98JH9CouOkb0KEgnZ34K8U42HWEZFLQFZ8v6ec9GixED27bHg 7',
      'bvXP1mSFkVIGfxlJZZ5ERYojgjeOVxV8K7wHuGUrusrpaRJL2gHFyad6GicYmFgFNJlibN8CcxLd1j2kireT6VxIgeN63Rr1G7vPQr9DfmUqDjDTGs8ka8gSpKsoYaUcd1FGEcmNx1B2r3w9SG0K56MmoBZklx2LmDcSJ4PL7y8gSdvYCWNuhDxcjQT3mUIVFyNrIMZ4mTCH98JH9CouOkb0KEgnZ34K8U42HWEZFLQFZ8v6ec9GixED27bHg 8',
      'bvXP1mSFkVIGfxlJZZ5ERYojgjeOVxV8K7wHuGUrusrpaRJL2gHFyad6GicYmFgFNJlibN8CcxLd1j2kireT6VxIgeN63Rr1G7vPQr9DfmUqDjDTGs8ka8gSpKsoYaUcd1FGEcmNx1B2r3w9SG0K56MmoBZklx2LmDcSJ4PL7y8gSdvYCWNuhDxcjQT3mUIVFyNrIMZ4mTCH98JH9CouOkb0KEgnZ34K8U42HWEZFLQFZ8v6ec9GixED27bHg 9',
      'bvXP1mSFkVIGfxlJZZ5ERYojgjeOVxV8K7wHuGUrusrpaRJL2gHFyad6GicYmFgFNJlibN8CcxLd1j2kireT6VxIgeN63Rr1G7vPQr9DfmUqDjDTGs8ka8gSpKsoYaUcd1FGEcmNx1B2r3w9SG0K56MmoBZklx2LmDcSJ4PL7y8gSdvYCWNuhDxcjQT3mUIVFyNrIMZ4mTCH98JH9CouOkb0KEgnZ34K8U42HWEZFLQFZ8v6ec9GixED27bH 10',
      'bvXP1mSFkVIGfxlJZZ5ERYojgjeOVxV8K7wHuGUrusrpaRJL2gHFyad6GicYmFgFNJlibN8CcxLd1j2kireT6VxIgeN63Rr1G7vPQr9DfmUqDjDTGs8ka8gSpKsoYaUcd1FGEcmNx1B2r3w9SG0K56MmoBZklx2LmDcSJ4PL7y8gSdvYCWNuhDxcjQT3mUIVFyNrIMZ4mTCH98JH9CouOkb0KEgnZ34K8U42HWEZFLQFZ8v6ec9GixED27bH 11',
    ]
    expect(importer.methods.makeHeaderUniqueAndValid(header)).toEqual(
      expectedHeader
    )
  })
  test('duplicate column names with exactly the allowed maximum name length must be correctly truncated with duplicate values', () => {
    // header with field names of exactly 255 char length
    const header = [
      'bvXP1mSFkVIGfxlJZZ5ERYojgjeOVxV8K7wHuGUrusrpaRJL2gHFyad6GicYmFgFNJlibN8CcxLd1j2kireT6VxIgeN63Rr1G7vPQr9DfmUqDjDTGs8ka8gSpKsoYaUcd1FGEcmNx1B2r3w9SG0K56MmoBZklx2LmDcSJ4PL7y8gSdvYCWNuhDxcjQT3mUIVFyNrIMZ4mTCH98JH9CouOkb0KEgnZ34K8U42HWEZFLQFZ8v6ec9GixED27bHgxy',
      'bvXP1mSFkVIGfxlJZZ5ERYojgjeOVxV8K7wHuGUrusrpaRJL2gHFyad6GicYmFgFNJlibN8CcxLd1j2kireT6VxIgeN63Rr1G7vPQr9DfmUqDjDTGs8ka8gSpKsoYaUcd1FGEcmNx1B2r3w9SG0K56MmoBZklx2LmDcSJ4PL7y8gSdvYCWNuhDxcjQT3mUIVFyNrIMZ4mTCH98JH9CouOkb0KEgnZ34K8U42HWEZFLQFZ8v6ec9GixED27bHgxy',
      'bvXP1mSFkVIGfxlJZZ5ERYojgjeOVxV8K7wHuGUrusrpaRJL2gHFyad6GicYmFgFNJlibN8CcxLd1j2kireT6VxIgeN63Rr1G7vPQr9DfmUqDjDTGs8ka8gSpKsoYaUcd1FGEcmNx1B2r3w9SG0K56MmoBZklx2LmDcSJ4PL7y8gSdvYCWNuhDxcjQT3mUIVFyNrIMZ4mTCH98JH9CouOkb0KEgnZ34K8U42HWEZFLQFZ8v6ec9GixED27bHgxy',
    ]

    const expectedHeader = [
      'bvXP1mSFkVIGfxlJZZ5ERYojgjeOVxV8K7wHuGUrusrpaRJL2gHFyad6GicYmFgFNJlibN8CcxLd1j2kireT6VxIgeN63Rr1G7vPQr9DfmUqDjDTGs8ka8gSpKsoYaUcd1FGEcmNx1B2r3w9SG0K56MmoBZklx2LmDcSJ4PL7y8gSdvYCWNuhDxcjQT3mUIVFyNrIMZ4mTCH98JH9CouOkb0KEgnZ34K8U42HWEZFLQFZ8v6ec9GixED27bHgxy',
      'bvXP1mSFkVIGfxlJZZ5ERYojgjeOVxV8K7wHuGUrusrpaRJL2gHFyad6GicYmFgFNJlibN8CcxLd1j2kireT6VxIgeN63Rr1G7vPQr9DfmUqDjDTGs8ka8gSpKsoYaUcd1FGEcmNx1B2r3w9SG0K56MmoBZklx2LmDcSJ4PL7y8gSdvYCWNuhDxcjQT3mUIVFyNrIMZ4mTCH98JH9CouOkb0KEgnZ34K8U42HWEZFLQFZ8v6ec9GixED27bHg 2',
      'bvXP1mSFkVIGfxlJZZ5ERYojgjeOVxV8K7wHuGUrusrpaRJL2gHFyad6GicYmFgFNJlibN8CcxLd1j2kireT6VxIgeN63Rr1G7vPQr9DfmUqDjDTGs8ka8gSpKsoYaUcd1FGEcmNx1B2r3w9SG0K56MmoBZklx2LmDcSJ4PL7y8gSdvYCWNuhDxcjQT3mUIVFyNrIMZ4mTCH98JH9CouOkb0KEgnZ34K8U42HWEZFLQFZ8v6ec9GixED27bHg 3',
    ]
    expect(importer.methods.makeHeaderUniqueAndValid(header)).toEqual(
      expectedHeader
    )
  })
})
