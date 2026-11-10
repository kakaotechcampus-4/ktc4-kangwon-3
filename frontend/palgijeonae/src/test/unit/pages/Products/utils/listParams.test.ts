import { SortType } from '@/api/products'
import { ResultStatus } from '@/api/types/common'
import { getLastPageIndex, type ListParams, MAX_PAGE_PARAM, parseListParams, toSearchParams } from '@/pages/Products/utils/listParams'

const parse = (query: string) => parseListParams(new URLSearchParams(query))

describe('parseListParams', () => {
  it('빈 쿼리는 전체·빈 검색어·최신순·첫 페이지(0)로 읽는다', () => {
    expect(parse('')).toEqual({ filter: 'all', keyword: '', sortType: SortType.Latest, page: 0 })
  })

  it('status, keyword, sort, page를 읽는다. page는 0부터 센 값으로 돌려준다', () => {
    expect(parse('status=RECHECK_REQUIRED&keyword=무드등&sort=OLDEST&page=3')).toEqual({
      filter: ResultStatus.RecheckRequired,
      keyword: '무드등',
      sortType: SortType.Oldest,
      page: 2,
    })
  })

  it('정해진 값이 아닌 status·sort는 기본값으로 읽는다', () => {
    expect(parse('status=WRONG&sort=WRONG')).toMatchObject({ filter: 'all', sortType: SortType.Latest })
  })

  it('같은 쿼리가 여러 번 오면 첫 번째 값만 쓴다', () => {
    expect(parse('status=RECHECK_REQUIRED&status=WRONG&page=2&page=5')).toMatchObject({ filter: ResultStatus.RecheckRequired, page: 1 })
  })

  it.each(['abc', '0', '-1', '1.5', '2e3', '0x10', ' 3', '3 ', '', String(MAX_PAGE_PARAM + 1)])('page가 "%s"이면 첫 페이지(0)로 읽는다', (value) => {
    expect(parse(`page=${encodeURIComponent(value)}`).page).toBe(0)
  })

  it('page가 상한(Java int 최댓값)이면 그대로 받는다', () => {
    expect(parse(`page=${MAX_PAGE_PARAM}`).page).toBe(MAX_PAGE_PARAM - 1)
  })
})

describe('toSearchParams', () => {
  const defaults: ListParams = { filter: 'all', keyword: '', sortType: SortType.Latest, page: 0 }

  it('조건이 모두 기본값이면 쿼리가 비어 있다', () => {
    expect(toSearchParams(defaults).toString()).toBe('')
  })

  it('기본값은 쓰지 않고, 기본이 아닌 값만 쓴다', () => {
    expect(toSearchParams({ ...defaults, sortType: SortType.Oldest }).toString()).toBe('sort=OLDEST')
    expect(toSearchParams({ ...defaults, filter: ResultStatus.RecheckRequired }).toString()).toBe('status=RECHECK_REQUIRED')
    expect(toSearchParams({ ...defaults, keyword: 'abc' }).toString()).toBe('keyword=abc')
  })

  it('page는 1부터 센 번호로 쓰고, 첫 페이지는 쓰지 않는다', () => {
    expect(toSearchParams({ ...defaults, page: 2 }).get('page')).toBe('3')
    expect(toSearchParams({ ...defaults, page: 0 }).has('page')).toBe(false)
  })

  it('쓴 쿼리를 다시 읽으면 원래 값 그대로다', () => {
    const original: ListParams = { filter: ResultStatus.DirectImportCertificationRequired, keyword: '검색 어&=?', sortType: SortType.Oldest, page: 4 }

    expect(parseListParams(toSearchParams(original))).toEqual(original)
    expect(parseListParams(toSearchParams(defaults))).toEqual(defaults)
  })
})

describe('getLastPageIndex', () => {
  it.each([
    [0, 0],
    [1, 0],
    [3, 2],
  ])('전체 페이지가 %i개면 마지막 페이지 번호는 %i다', (totalPages, expected) => {
    expect(getLastPageIndex(totalPages)).toBe(expected)
  })
})
