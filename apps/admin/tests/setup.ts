import '@testing-library/jest-dom/vitest'

// jsdom does not implement <dialog>'s showModal()/close() (only the `open`
// attribute reflection). Focus movement itself is handled explicitly by
// useDialogElement, not by this polyfill.
if (typeof HTMLDialogElement !== 'undefined' && !HTMLDialogElement.prototype.showModal) {
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement): void {
    this.setAttribute('open', '')
  }
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement): void {
    this.removeAttribute('open')
    this.dispatchEvent(new Event('close'))
  }
}
