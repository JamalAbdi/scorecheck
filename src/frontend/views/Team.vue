<template>
  <section class="panel">
    <router-link to="/" class="back">← Back to teams</router-link>

    <h2 v-if="team">{{ team.name }} <span class="league">{{ team.league }}</span></h2>
    <p v-if="loading">Loading team...</p>
    <p v-else-if="error">{{ error }}</p>

    <div v-if="team" class="grid">
      <div>
        <h3>Players</h3>
        <table class="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Position</th>
              <th v-for="stat in playerStats" :key="stat">{{ stat.toUpperCase() }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="player in team.players" :key="player.name">
              <td>{{ player.name }}</td>
              <td>{{ player.position }}</td>
              <td v-for="stat in playerStats" :key="stat + player.name">
                {{ player.stats?.[stat] ?? '-' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div>
        <h3>Games</h3>
        <div class="games">
          <div class="game" v-for="game in team.games" :key="game.date + game.opponent">
            <div class="game-meta">
              <strong>{{ game.date }}</strong>
              <span>{{ game.home ? 'Home' : 'Away' }} vs {{ game.opponent }}</span>
            </div>
            <div class="game-score">
              <span v-if="game.status === 'played'">Final: {{ game.score }}</span>
              <span v-else>Upcoming</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script>
export default {
  name: 'TeamView',
}
</script>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const team = ref(null)
const loading = ref(true)
const error = ref('')

const playerStats = computed(() => {
  if (!team.value || team.value.players.length === 0) {
    return []
  }
  const sample = team.value.players[0]
  return Object.keys(sample.stats || {})
})

const loadTeam = async () => {
  try {
    const league = route.params.league
    const teamId = route.params.id
    const response = await fetch(`http://localhost:8000/api/leagues/${league}/teams/${teamId}`)
    if (!response.ok) {
      const message = await response.text()
      throw new Error(message || `API error: ${response.status}`)
    }
    team.value = await response.json()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unknown error'
  } finally {
    loading.value = false
  }
}

onMounted(loadTeam)
</script>

<style scoped>
.panel {
  background: #fff;
  border-radius: 16px;
  padding: 20px 24px;
  box-shadow: 0 10px 20px rgba(15, 23, 42, 0.08);
}

.back {
  display: inline-block;
  margin-bottom: 12px;
  color: #2563eb;
  text-decoration: none;
  font-weight: 600;
}

.league {
  font-size: 14px;
  color: #6b7280;
  margin-left: 8px;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 24px;
}

.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.table th,
.table td {
  text-align: left;
  padding: 8px 6px;
  border-bottom: 1px solid #eef2f6;
}

.games {
  display: grid;
  gap: 12px;
}

.game {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 12px 14px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.game-meta span {
  display: block;
  color: #6b7280;
  margin-top: 4px;
}

.game-score {
  font-weight: 600;
}
</style>
