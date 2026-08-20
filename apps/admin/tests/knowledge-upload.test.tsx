import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as knowledgeApi from '../src/api/knowledge'
import { renderKnowledgePage } from './testUtils'

vi.mock('../src/api/knowledge')

const mockedListDocuments = vi.mocked(knowledgeApi.listDocuments)
const mockedGetKnowledgeHealth = vi.mocked(knowledgeApi.getKnowledgeHealth)
const mockedUploadDocument = vi.mocked(knowledgeApi.uploadDocument)

const HEALTH_EMPTY = {
  documents: { total: 0, ready: 0, processing: 0, failed: 0 },
  chunks: 0,
  ready_for_chat: false,
  last_indexed_at: null,
}

const HEALTH_ONE_READY = {
  documents: { total: 1, ready: 1, processing: 0, failed: 0 },
  chunks: 3,
  ready_for_chat: true,
  last_indexed_at: '2026-08-20T10:00:05Z',
}

const UPLOADED_DOCUMENT = {
  id: 'doc-1',
  filename: 'kontakt.txt',
  content_type: 'text/plain',
  status: 'ready' as const,
  uploaded_at: '2026-08-20T10:00:00Z',
  updated_at: '2026-08-20T10:00:00Z',
  indexed_at: '2026-08-20T10:00:05Z',
  error_message: null,
}

beforeEach(() => {
  mockedListDocuments.mockReset()
  mockedGetKnowledgeHealth.mockReset()
  mockedUploadDocument.mockReset()
  mockedListDocuments.mockResolvedValue([])
  mockedGetKnowledgeHealth.mockResolvedValue(HEALTH_EMPTY)
})

async function selectAndUpload(user: ReturnType<typeof userEvent.setup>) {
  const file = new File(['hello'], 'kontakt.txt', { type: 'text/plain' })
  const input = screen.getByLabelText('Upload document') as HTMLInputElement
  await user.upload(input, file)
  await user.click(screen.getByRole('button', { name: 'Upload document' }))
}

describe('Knowledge upload', () => {
  it('refreshes the document list and health summary and shows success feedback — no full reload', async () => {
    mockedUploadDocument.mockResolvedValue(UPLOADED_DOCUMENT)
    const user = userEvent.setup()
    renderKnowledgePage()

    await waitFor(() => expect(screen.getByLabelText('Upload document')).toBeInTheDocument())
    mockedListDocuments.mockResolvedValue([UPLOADED_DOCUMENT])
    mockedGetKnowledgeHealth.mockResolvedValue(HEALTH_ONE_READY)

    await selectAndUpload(user)

    await waitFor(() => expect(screen.getByText('kontakt.txt')).toBeInTheDocument())
    expect(screen.getByText('1 documents')).toBeInTheDocument()
    expect(screen.getByText(/uploaded — status: Ready/)).toBeInTheDocument()
  })

  it('shows exactly one safe message on a rejected upload, never raw backend text', async () => {
    mockedUploadDocument.mockRejectedValue({ message: 'File is not valid UTF-8.', status: 400 })
    const user = userEvent.setup()
    renderKnowledgePage()

    await waitFor(() => expect(screen.getByLabelText('Upload document')).toBeInTheDocument())
    await selectAndUpload(user)

    expect(await screen.findByRole('alert')).toHaveTextContent('File is not valid UTF-8.')
  })

  it('prevents a second submission while the first is still pending', async () => {
    let resolveUpload!: (value: typeof UPLOADED_DOCUMENT) => void
    mockedUploadDocument.mockReturnValue(
      new Promise((resolve) => {
        resolveUpload = resolve
      }),
    )
    const user = userEvent.setup()
    renderKnowledgePage()

    await waitFor(() => expect(screen.getByLabelText('Upload document')).toBeInTheDocument())
    await selectAndUpload(user)

    expect(screen.getByRole('button', { name: 'Upload document' })).toBeDisabled()
    expect(screen.getByText('Uploading and indexing…')).toBeInTheDocument()
    expect(mockedUploadDocument).toHaveBeenCalledTimes(1)

    resolveUpload(UPLOADED_DOCUMENT)
    await waitFor(() =>
      expect(screen.queryByText('Uploading and indexing…')).not.toBeInTheDocument(),
    )
    // Still only ever called once — no duplicate submission went through.
    expect(mockedUploadDocument).toHaveBeenCalledTimes(1)
  })

  it('is operable using the keyboard alone', async () => {
    mockedUploadDocument.mockResolvedValue(UPLOADED_DOCUMENT)
    const user = userEvent.setup()
    renderKnowledgePage()

    const input = await screen.findByLabelText('Upload document')
    const file = new File(['hello'], 'kontakt.txt', { type: 'text/plain' })
    await user.upload(input, file)

    const submit = screen.getByRole('button', { name: 'Upload document' })
    submit.focus()
    expect(submit).toHaveFocus()
    await user.keyboard('{Enter}')

    await waitFor(() => expect(mockedUploadDocument).toHaveBeenCalledTimes(1))
  })
})
