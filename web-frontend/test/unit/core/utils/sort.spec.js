import { sortNumbersAndUuid1Asc } from '@baserow/modules/core/utils/sort'
//import { uuid as uuidv1 } from '@baserow/modules/core/utils/string'

import { monotonicFactory } from 'ulid'

const uuidv1 = monotonicFactory()

describe('sort', () => {
  it('should sort numbers correctly', () => {
    const numbers = [{ id: 5 }, { id: 1 }, { id: 4 }, { id: 3 }, { id: 2 }]
    numbers.sort(sortNumbersAndUuid1Asc)
    expect(numbers).toEqual([
      { id: 1 },
      { id: 2 },
      { id: 3 },
      { id: 4 },
      { id: 5 },
    ])
  })

  it('should sort uuid v1 correctly', () => {
    const seq = [uuidv1(), uuidv1(), uuidv1(), uuidv1(), uuidv1()]
    const numbers = [
      { id: seq[4] },
      { id: seq[1] },
      { id: seq[3] },
      { id: seq[0] },
      { id: seq[2] },
    ]
    numbers.sort(sortNumbersAndUuid1Asc)
    expect(numbers).toEqual([
      { id: seq[0] },
      { id: seq[1] },
      { id: seq[2] },
      { id: seq[3] },
      { id: seq[4] },
    ])
  })
  it('should sort numbers and uuid v1 correctly', () => {
    const seq = [uuidv1(), uuidv1(), uuidv1(), uuidv1(), uuidv1()]
    const numbers = [
      { id: seq[4] },
      { id: 3 },
      { id: seq[1] },
      { id: 2 },
      { id: seq[3] },
      { id: seq[0] },
      { id: 1 },
      { id: seq[2] },
      { id: 4 },
    ]
    numbers.sort(sortNumbersAndUuid1Asc)
    expect(numbers).toEqual([
      { id: 1 },
      { id: 2 },
      { id: 3 },
      { id: 4 },
      { id: seq[0] },
      { id: seq[1] },
      { id: seq[2] },
      { id: seq[3] },
      { id: seq[4] },
    ])
  })
})
