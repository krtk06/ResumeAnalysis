import { useEffect, useRef, useState } from 'react'

const PREDEFINED_ROLES = [
  'Software Engineer',
  'Frontend Developer',
  'Backend Developer',
  'Full Stack Developer',
  'Data Scientist',
  'Machine Learning Engineer',
  'DevOps Engineer',
  'Product Manager',
  'UI/UX Designer',
  'Data Analyst'
]

function RoleSelector({ value, onChange, roles = PREDEFINED_ROLES }) {
  const [isCustom, setIsCustom] = useState(false)
  const [customValue, setCustomValue] = useState('')
  const [isOpen, setIsOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const containerRef = useRef(null)
  const menuRef = useRef(null)
  const options = [...roles, 'Custom role…']
  const selectedIndex = isCustom ? options.length - 1 : roles.indexOf(value)
  const selectedLabel = isCustom ? (customValue || 'Custom role…') : (value || 'Select a role')

  useEffect(() => {
    if (value && !roles.includes(value)) {
      setIsCustom(true)
      setCustomValue(value)
    }
  }, [value, roles])

  useEffect(() => {
    if (!isOpen) return undefined

    const handleOutsideClick = (event) => {
      if (!containerRef.current?.contains(event.target)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('pointerdown', handleOutsideClick)
    return () => document.removeEventListener('pointerdown', handleOutsideClick)
  }, [isOpen])

  useEffect(() => {
    if (isOpen) menuRef.current?.focus()
  }, [isOpen])

  const openMenu = () => {
    setActiveIndex(selectedIndex >= 0 ? selectedIndex : 0)
    setIsOpen(true)
  }

  const chooseRole = (index) => {
    if (index === roles.length) {
      setIsCustom(true)
      onChange(customValue)
    } else {
      setIsCustom(false)
      onChange(roles[index])
    }
    setIsOpen(false)
  }

  const handleTriggerKeyDown = (event) => {
    if (event.key === 'ArrowDown' || event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      openMenu()
    }
  }

  const handleMenuKeyDown = (event) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActiveIndex((index) => Math.min(index + 1, options.length - 1))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActiveIndex((index) => Math.max(index - 1, 0))
    } else if (event.key === 'Home') {
      event.preventDefault()
      setActiveIndex(0)
    } else if (event.key === 'End') {
      event.preventDefault()
      setActiveIndex(options.length - 1)
    } else if (event.key === 'Enter') {
      event.preventDefault()
      chooseRole(activeIndex)
    } else if (event.key === 'Escape') {
      event.preventDefault()
      setIsOpen(false)
    }
  }

  const handleCustomChange = (event) => {
    const nextValue = event.target.value
    setCustomValue(nextValue)
    onChange(nextValue)
  }

  const fieldClass = `
    w-full appearance-none border-0 border-b border-rule bg-transparent
    px-1 py-3 text-base font-medium text-ink
    focus:border-ink focus:outline-none
  `

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-[minmax(7rem,auto)_1fr] items-baseline gap-x-6">
        <span className="font-spec text-xs uppercase tracking-[0.14em] text-ink-faint">
          From roster
        </span>
        <div ref={containerRef} className="relative">
          <button
            id="role-select"
            type="button"
            role="combobox"
            aria-label="From roster"
            aria-expanded={isOpen}
            aria-controls="role-menu"
            aria-haspopup="listbox"
            aria-activedescendant={isOpen ? `role-option-${activeIndex}` : undefined}
            onClick={() => (isOpen ? setIsOpen(false) : openMenu())}
            onKeyDown={handleTriggerKeyDown}
            className={`${fieldClass} flex cursor-pointer items-center justify-between gap-4 text-left`}
          >
            <span className={!value && !isCustom ? 'text-ink-faint' : ''}>{selectedLabel}</span>
            <svg aria-hidden="true" className={`h-3.5 w-3.5 shrink-0 text-ink transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="square" d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {isOpen && (
            <div
              id="role-menu"
              data-testid="role-menu"
              ref={menuRef}
              role="listbox"
              aria-label="Available target roles"
              tabIndex={-1}
              onKeyDown={handleMenuKeyDown}
              className="absolute left-0 right-0 top-full z-20 mt-2 max-h-72 overflow-y-auto border border-ink bg-stock p-1 text-ink"
            >
              {options.map((option, index) => {
                const isSelected = index === selectedIndex
                const isActive = index === activeIndex

                return (
                  <button
                    key={option}
                    id={`role-option-${index}`}
                    type="button"
                    role="option"
                    aria-selected={isSelected}
                    onMouseEnter={() => setActiveIndex(index)}
                    onClick={() => chooseRole(index)}
                    className={`role-option block w-full px-3 py-2 text-left text-sm transition-colors duration-150 ${
                      isActive ? 'role-option-active bg-ink text-stock' : 'text-ink hover:bg-stock-deep'
                    }`}
                  >
                    <span className="flex items-center justify-between gap-3">
                      {option}
                      {isSelected && <span aria-hidden="true" className="font-spec text-[10px] uppercase tracking-[0.12em] text-proof">Set</span>}
                    </span>
                  </button>
                )
              })}
            </div>
          )}
        </div>
      </div>

      {isCustom && (
        <div className="grid grid-cols-[minmax(7rem,auto)_1fr] items-baseline gap-x-6">
          <label
            htmlFor="role-custom"
            className="font-spec text-xs uppercase tracking-[0.14em] text-ink-faint"
          >
            Or write it in
          </label>
          <input
            id="role-custom"
            type="text"
            value={customValue}
            onChange={handleCustomChange}
            placeholder="e.g., Security Analyst"
            className={fieldClass}
          />
        </div>
      )}
    </div>
  )
}

export default RoleSelector
