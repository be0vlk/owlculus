<template>
  <div class="prototype-variant-b">
    <header><slot name="identity" /></header>
    <section class="case-file">
      <nav aria-label="Case workspaces"><slot name="tabs" /></nav>
      <div class="file-content"><slot /></div>
    </section>
  </div>
</template>
<style scoped>
.prototype-variant-b {
  min-height: 100vh;
  padding: 30px 32px 110px;
  background: rgb(var(--v-theme-on-surface), 0.035);
}

header {
  margin: 0 8px 28px;
}

.case-file {
  border: 1px solid rgb(var(--v-border-color), var(--v-border-opacity));
  border-radius: 12px;
  background: rgb(var(--v-theme-surface));
}

nav {
  border-bottom: 1px solid rgb(var(--v-border-color), var(--v-border-opacity));
  padding: 7px 12px 0;
}

.file-content {
  padding: 24px;
}

@media (width <= 600px) {
  .prototype-variant-b {
    padding: 18px 10px 100px;
  }

  header {
    margin: 0 4px 20px;
  }

  .file-content {
    padding: 16px 10px;
  }

  nav {
    padding-inline: 0;
  }
}
</style>
