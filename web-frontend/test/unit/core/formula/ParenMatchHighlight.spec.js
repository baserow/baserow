import {
  getParenType,
  collectDOMParenPairs,
} from '@baserow/modules/core/components/formula/extensions/ParenMatchHighlightExtension'

// ── DOM element helpers ─────────────────────────────────────────────

function createFuncOpener(label = 'func(') {
  const el = document.createElement('span')
  el.classList.add('function-formula-component')
  el.textContent = label
  return el
}

function createFuncCloser() {
  const el = document.createElement('span')
  el.dataset.formulaClosingParen = 'true'
  el.textContent = ')'
  return el
}

function createGroupOpener() {
  const el = document.createElement('span')
  el.dataset.groupOpeningParen = 'true'
  el.textContent = '('
  return el
}

function createGroupCloser() {
  const el = document.createElement('span')
  el.dataset.groupClosingParen = 'true'
  el.textContent = ')'
  return el
}

function createContainer(...children) {
  const root = document.createElement('div')
  children.forEach((child) => root.appendChild(child))
  return root
}

// ── getParenType ────────────────────────────────────────────────────

describe('getParenType', () => {
  it('returns "function" for a function opener', () => {
    expect(getParenType(createFuncOpener())).toBe('function')
  })

  it('returns "function" for a function closer', () => {
    expect(getParenType(createFuncCloser())).toBe('function')
  })

  it('returns "group" for a group opener', () => {
    expect(getParenType(createGroupOpener())).toBe('group')
  })

  it('returns "group" for a group closer', () => {
    expect(getParenType(createGroupCloser())).toBe('group')
  })
})

// ── collectDOMParenPairs ────────────────────────────────────────────

describe('collectDOMParenPairs', () => {
  it('returns empty map when no paren elements exist', () => {
    const root = createContainer(document.createElement('span'))
    const pairs = collectDOMParenPairs(root)
    expect(pairs.size).toBe(0)
  })

  it('pairs a function opener with its closer', () => {
    const opener = createFuncOpener()
    const closer = createFuncCloser()
    const root = createContainer(opener, closer)

    const pairs = collectDOMParenPairs(root)
    expect(pairs.get(opener)).toBe(closer)
    expect(pairs.get(closer)).toBe(opener)
  })

  it('pairs a group opener with its closer', () => {
    const opener = createGroupOpener()
    const closer = createGroupCloser()
    const root = createContainer(opener, closer)

    const pairs = collectDOMParenPairs(root)
    expect(pairs.get(opener)).toBe(closer)
    expect(pairs.get(closer)).toBe(opener)
  })

  it('does not pair a function opener with a group closer', () => {
    const opener = createFuncOpener()
    const closer = createGroupCloser()
    const root = createContainer(opener, closer)

    const pairs = collectDOMParenPairs(root)
    expect(pairs.size).toBe(0)
  })

  it('does not pair a group opener with a function closer', () => {
    const opener = createGroupOpener()
    const closer = createFuncCloser()
    const root = createContainer(opener, closer)

    const pairs = collectDOMParenPairs(root)
    expect(pairs.size).toBe(0)
  })

  it('handles nested function inside group: ( func() )', () => {
    const groupOpen = createGroupOpener()
    const funcOpen = createFuncOpener()
    const funcClose = createFuncCloser()
    const groupClose = createGroupCloser()
    const root = createContainer(groupOpen, funcOpen, funcClose, groupClose)

    const pairs = collectDOMParenPairs(root)
    expect(pairs.get(funcOpen)).toBe(funcClose)
    expect(pairs.get(funcClose)).toBe(funcOpen)
    expect(pairs.get(groupOpen)).toBe(groupClose)
    expect(pairs.get(groupClose)).toBe(groupOpen)
    expect(pairs.size).toBe(4)
  })

  it('handles nested group inside function: func( (x) )', () => {
    const funcOpen = createFuncOpener()
    const groupOpen = createGroupOpener()
    const groupClose = createGroupCloser()
    const funcClose = createFuncCloser()
    const root = createContainer(funcOpen, groupOpen, groupClose, funcClose)

    const pairs = collectDOMParenPairs(root)
    expect(pairs.get(funcOpen)).toBe(funcClose)
    expect(pairs.get(groupOpen)).toBe(groupClose)
    expect(pairs.size).toBe(4)
  })

  it('handles deeply nested: ( ( func( func() ) ) )', () => {
    const g1 = createGroupOpener()
    const g2 = createGroupOpener()
    const f1 = createFuncOpener('outer(')
    const f2 = createFuncOpener('inner(')
    const f2c = createFuncCloser()
    const f1c = createFuncCloser()
    const g2c = createGroupCloser()
    const g1c = createGroupCloser()
    const root = createContainer(g1, g2, f1, f2, f2c, f1c, g2c, g1c)

    const pairs = collectDOMParenPairs(root)
    expect(pairs.get(g1)).toBe(g1c)
    expect(pairs.get(g2)).toBe(g2c)
    expect(pairs.get(f1)).toBe(f1c)
    expect(pairs.get(f2)).toBe(f2c)
    expect(pairs.size).toBe(8)
  })

  it('leaves unmatched opener unpaired when its closer is missing', () => {
    const funcOpen = createFuncOpener()
    const groupClose = createGroupCloser()
    const root = createContainer(funcOpen, groupClose)

    const pairs = collectDOMParenPairs(root)
    expect(pairs.has(funcOpen)).toBe(false)
    expect(pairs.has(groupClose)).toBe(false)
  })

  it('leaves orphan opener unpaired (no closer at all)', () => {
    const opener = createFuncOpener()
    const root = createContainer(opener)

    const pairs = collectDOMParenPairs(root)
    expect(pairs.size).toBe(0)
  })

  it('leaves orphan closer unpaired (no opener at all)', () => {
    const closer = createFuncCloser()
    const root = createContainer(closer)

    const pairs = collectDOMParenPairs(root)
    expect(pairs.size).toBe(0)
  })

  it('pairs siblings: func() func()', () => {
    const f1 = createFuncOpener('a(')
    const f1c = createFuncCloser()
    const f2 = createFuncOpener('b(')
    const f2c = createFuncCloser()
    const root = createContainer(f1, f1c, f2, f2c)

    const pairs = collectDOMParenPairs(root)
    expect(pairs.get(f1)).toBe(f1c)
    expect(pairs.get(f2)).toBe(f2c)
    expect(pairs.size).toBe(4)
  })

  it('pairs correctly when missing inner closer: ( func( ) )', () => {
    // func( has no matching function closer, only a group closer follows
    const groupOpen = createGroupOpener()
    const funcOpen = createFuncOpener()
    const groupClose = createGroupCloser()
    const root = createContainer(groupOpen, funcOpen, groupClose)

    const pairs = collectDOMParenPairs(root)
    // func( cannot pair with group closer (type mismatch)
    // group opener cannot pair with group closer because func( is still on the stack
    expect(pairs.has(funcOpen)).toBe(false)
    expect(pairs.has(groupOpen)).toBe(false)
    expect(pairs.size).toBe(0)
  })

  it('handles the if() regression case: ( ( if( today() ) ) )', () => {
    // Missing if's closer — the group closers should still pair with group openers
    const g1 = createGroupOpener()
    const g2 = createGroupOpener()
    const ifOpen = createFuncOpener('if(')
    const todayOpen = createFuncOpener('today(')
    const todayClose = createFuncCloser()
    // if's closer is missing
    const g2c = createGroupCloser()
    const g1c = createGroupCloser()
    const root = createContainer(
      g1,
      g2,
      ifOpen,
      todayOpen,
      todayClose,
      g2c,
      g1c
    )

    const pairs = collectDOMParenPairs(root)
    // today() should be paired
    expect(pairs.get(todayOpen)).toBe(todayClose)
    expect(pairs.get(todayClose)).toBe(todayOpen)
    // if( has no matching function closer → unpaired
    expect(pairs.has(ifOpen)).toBe(false)
    // group closers can't match because if( is blocking the stack
    expect(pairs.has(g1)).toBe(false)
    expect(pairs.has(g2)).toBe(false)
  })
})
