import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { downloadBlob } from '../download'

describe('downloadBlob', () => {
  let clickedAnchor

  beforeEach(() => {
    clickedAnchor = null
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: vi.fn(() => 'blob:download'),
    })
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      value: vi.fn(),
    })
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function () {
      clickedAnchor = this
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('uses the filename supplied by Content-Disposition', () => {
    const blob = new Blob(['export'], { type: 'text/csv' })

    downloadBlob(
      {
        blob,
        headers: { 'content-disposition': 'attachment; filename="CASE-001-entities.csv"' },
      },
      'entities.csv',
    )

    expect(URL.createObjectURL).toHaveBeenCalledWith(blob)
    expect(clickedAnchor.download).toBe('CASE-001-entities.csv')
    expect(clickedAnchor.href).toBe('blob:download')
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:download')
    expect(document.body.contains(clickedAnchor)).toBe(false)
  })

  it('decodes a UTF-8 Content-Disposition filename', () => {
    downloadBlob(
      {
        blob: new Blob(['export']),
        headers: { get: () => "attachment; filename*=UTF-8''M%C3%BCnchen-entities.json" },
      },
      'entities.json',
    )

    expect(clickedAnchor.download).toBe('München-entities.json')
  })

  it('uses the fallback when the response has no filename', () => {
    downloadBlob({ blob: new Blob(['export']), headers: {} }, 'entities.csv')

    expect(clickedAnchor.download).toBe('entities.csv')
  })
})
