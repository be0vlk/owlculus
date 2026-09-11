<template>
  <div class="prototype-variant-c">
    <header><slot name="identity" /></header>
    <div class="rail-body">
      <nav aria-label="Case workspaces">
        <span class="rail-caption">WORKSPACE</span><slot name="tabs" />
      </nav>
      <div class="rail-content"><slot /></div>
    </div>
  </div>
</template>
<style scoped>
.prototype-variant-c {
  padding-bottom: 100px;
}

header {
  padding: 22px 26px;
  border-bottom: 1px solid rgb(var(--v-border-color), var(--v-border-opacity));
}

.rail-body {
  display: grid;
  grid-template-columns: 172px minmax(0, 1fr);
  min-height: calc(100vh - 185px);
}

nav {
  padding: 24px 10px;
  border-right: 1px solid rgb(var(--v-border-color), var(--v-border-opacity));
  background: rgb(var(--v-theme-on-surface), 0.025);
}

.rail-caption {
  display: block;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1.8px;
  opacity: 0.6;
  margin: 0 14px 16px;
}

.rail-content {
  min-width: 0;
  padding: 25px 24px;
}

@media (width <= 1200px) {
  .rail-body {
    grid-template-columns: 144px minmax(0, 1fr);
  }

  .rail-content {
    padding-inline: 16px;
  }
}

@media (width <= 700px) {
  header {
    padding: 18px 14px;
  }

  .rail-body {
    display: block;
  }

  nav {
    padding: 0 10px;
    border-right: 0;
    border-bottom: 1px solid rgb(var(--v-border-color), var(--v-border-opacity));
  }

  .rail-caption {
    display: none;
  }

  .rail-content {
    padding: 20px 14px;
  }
}
</style>
