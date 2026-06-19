<script setup lang="ts">
import { RouterView } from 'vue-router'
</script>

<template>
  <div id="app">
    <header>
      <h1>Joblogic Automation</h1>
    </header>
    <main>
      <RouterView />
    </main>
  </div>
</template>

<style>
:root {
  font-family: Inter, system-ui, -apple-system, sans-serif;
  color: #213547;
  background-color: #ffffff;
}

body {
  margin: 0;
  padding: 0;
}

#app {
  max-width: 1280px;
  margin: 0 auto;
  padding: 2rem;
}

header h1 {
  font-size: 1.5rem;
  margin-bottom: 1rem;
}
</style>
