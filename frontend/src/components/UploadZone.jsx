import { useState, useRef } from 'react'

function CropMark({ className }) {
  return (
    <svg
      aria-hidden="true"
      className={`absolute h-4 w-4 text-ink ${className}`}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1"
    >
      <path d="M0 5h5M5 0v5" />
    </svg>
  )
}

function UploadZone({ onFileSelect, selectedFile }) {
  const [isDragging, setIsDragging] = useState(false)
  const [notice, setNotice] = useState(null)
  const inputRef = useRef(null)

  const handleDragOver = (e) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = (e) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setIsDragging(false)
    validateAndSetFile(e.dataTransfer.files[0])
  }

  const handleFileChange = (e) => {
    if (e.target.files.length > 0) {
      validateAndSetFile(e.target.files[0])
    }
  }

  const validateAndSetFile = (file) => {
    if (!file) return
    setNotice(null)

    const allowedExtensions = ['.pdf', '.docx']
    const ext = file.name.toLowerCase().slice(file.name.lastIndexOf('.'))

    if (!allowedExtensions.includes(ext)) {
      setNotice(`${file.name} is not a PDF or DOCX. Export the resume to one of those formats and drop it again.`)
      return
    }

    if (file.size > 10 * 1024 * 1024) {
      setNotice(`${file.name} is ${(file.size / (1024 * 1024)).toFixed(1)}MB — over the 10MB press limit. Compress or export a lighter copy.`)
      return
    }

    onFileSelect(file)
  }

  const handleClick = () => {
    inputRef.current?.click()
  }

  const handleRemove = (e) => {
    e.stopPropagation()
    setNotice(null)
    onFileSelect(null)
  }

  return (
    <div>
      <div
        data-testid="upload-surface"
        data-animated="true"
        onClick={handleClick}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            handleClick()
          }
        }}
        role="button"
        tabIndex={0}
        aria-label={selectedFile ? `Change file, ${selectedFile.name} selected` : 'Upload resume, PDF or DOCX up to 10 megabytes'}
        className={`
          upload-surface group relative cursor-pointer overflow-hidden border border-ink transition-all duration-300
          ${isDragging ? 'bg-ink text-stock' : 'bg-transparent text-ink hover:bg-stock-deep'}
        `}
      >
        <span className="upload-beam" aria-hidden="true" />
        <CropMark className="-left-2 -top-2" />
        <CropMark className="-right-2 -top-2 rotate-90" />
        <CropMark className="-bottom-2 -right-2 rotate-180" />
        <CropMark className="-bottom-2 -left-2 -rotate-90" />

        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx"
          onChange={handleFileChange}
          className="hidden"
        />

        {selectedFile ? (
          <div className="flex items-center justify-between gap-4 px-5 py-6">
            <div className="flex min-w-0 items-center gap-4">
              <span className="file-type-mark" aria-hidden="true">
                {selectedFile.name.toLowerCase().endsWith('.pdf') ? 'PDF' : 'DOCX'}
              </span>
              <div className="min-w-0">
                <p className="truncate font-medium">{selectedFile.name}</p>
                <p className="mt-1 font-spec text-xs text-ink-faint">
                  {(selectedFile.size / 1024).toFixed(1)} KB · received · click to replace
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={handleRemove}
              aria-label={`Remove ${selectedFile.name}`}
              className="shrink-0 border border-rule px-2 py-1 font-spec text-[10px] uppercase tracking-[0.14em] text-ink-faint transition-colors hover:border-proof hover:text-proof"
            >
              Remove
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3 px-6 py-14 text-center">
            <svg aria-hidden="true" className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.25">
              <path strokeLinecap="square" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <p className="text-lg font-bold uppercase tracking-normal [font-stretch:80%]">
              Drop the resume on the sheet
            </p>
            <p className="font-spec text-xs text-ink-faint">
              PDF or DOCX · max 10MB · click to browse
            </p>
            <span className="mt-2 font-spec text-[10px] uppercase tracking-[0.14em] text-proof transition-transform duration-300 group-hover:translate-y-0">
              Drop to add
            </span>
          </div>
        )}
      </div>

      {notice && (
        <p role="alert" className="mt-3 flex items-start gap-2 text-sm text-proof-deep">
          <span aria-hidden="true" className="font-spec font-bold">#</span>
          {notice}
        </p>
      )}
    </div>
  )
}

export default UploadZone
