<template>
  <div class="app">
    <header class="header">
      <h1>Scorecheck</h1>
    </header>

    <main class="content">
      <router-view />
    </main>
  </div>
</template>

<style>
:root {
  color-scheme: light;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: #1d1d1f;
  background: #f5f6f8;
}

.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.header {
  background: #111827;
  color: #fff;
  padding: 20px 32px;
}

.header h1 {
  margin: 0;
  font-size: 22px;
}

.content {
  flex: 1;
  padding: 24px 32px 48px;
}
</style>

