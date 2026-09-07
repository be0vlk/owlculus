<template>
  <div class="prototype-variant-a">
    <header><slot name="identity" /></header>
    <nav aria-label="Case workspaces"><slot name="tabs" /></nav>
    <div class="open-content"><slot /></div>
  </div>
</template>
<style scoped>
.prototype-variant-a {
  padding: 26px 30px 110px;
}

header {
  margin-bottom: 22px;
}

nav {
  border-bottom: 1px solid rgb(var(--v-border-color), var(--v-border-opacity));
}

.open-content {
  padding-top: 24px;
}

@media (width <= 600px) {
  .prototype-variant-a {
    padding: 18px 14px 100px;
  }
}
</style>
