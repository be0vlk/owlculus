export const marker = 'baseline'

document.documentElement.dataset.e2eHmrProbe = marker

if (import.meta.hot) {
  import.meta.hot.accept((updatedModule) => {
    document.documentElement.dataset.e2eHmrProbe = updatedModule.marker
  })
}
