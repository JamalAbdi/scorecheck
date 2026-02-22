<template>
  <section class="hero">
    <div class="hero-card">
      <img alt="Raptors" src="../assets/raptors.png" class="hero-img">
      <h2>Toronto Raptors</h2>
    </div>
    <div class="hero-card">
      <img alt="Maple Leafs" src="../assets/maple-leafs.png" class="hero-img">
      <h2>Toronto Maple Leafs</h2>
    </div>
    <div class="hero-card">
      <img alt="Blue Jays" src="../assets/bluejays.png" class="hero-img">
      <h2>Toronto Blue Jays</h2>
    </div>
  </section>

  <section class="panel">
    <h2>Teams</h2>
    <p v-if="loading">Loading teams...</p>
    <p v-else-if="error">{{ error }}</p>
    <ul v-else class="team-list">
      <li v-for="team in teams" :key="team.id">
        <router-link :to="`/teams/${team.id}`">
          {{ team.name }} — {{ team.league }}
        </router-link>
      </li>
    </ul>
  </section>
</template>

<script>
export default {
  name: 'HomeView',
}
</script>

<script setup>
import { onMounted, ref } from 'vue'

const teams = ref([])
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    const response = await fetch('http://localhost:8000/api/teams')
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`)
    }
    const data = await response.json()
    teams.value = data.teams || []
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unknown error'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.hero {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  margin-bottom: 32px;
}

.hero-card {
  background: #fff;
  border-radius: 16px;
  padding: 16px;
  box-shadow: 0 10px 20px rgba(15, 23, 42, 0.08);
  text-align: center;
}

.hero-img {
  width: 120px;
  height: auto;
}

.panel {
  background: #fff;
  border-radius: 16px;
  padding: 20px 24px;
  box-shadow: 0 10px 20px rgba(15, 23, 42, 0.08);
}

.team-list {
  list-style: none;
  padding: 0;
  margin: 12px 0 0;
}

.team-list li {
  padding: 10px 0;
  border-bottom: 1px solid #eef2f6;
}

.team-list li:last-child {
  border-bottom: none;
}

.team-list a {
  color: #111827;
  text-decoration: none;
  font-weight: 600;
}

.team-list a:hover {
  color: #2563eb;
}
</style>
