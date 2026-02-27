<template>
  <section class="panel">
    <router-link to="/" class="back">← Back to games</router-link>

    <h2 v-if="team">
      <img v-if="team.logo" :src="team.logo" :alt="`${team.name} logo`" class="team-header-logo" />
      {{ team.name }}
      <span class="league">{{ team.league }}</span>
      <span class="record" v-if="teamRecord">{{ teamRecord }}</span>
    </h2>
    <p v-if="loading">Loading team...</p>
    <p v-else-if="error">{{ error }}</p>

    <div v-if="team" class="grid">
      <div>
        <h3>Players</h3>
        <div class="game-select-wrap" v-if="playedGames.length > 0">
          <label for="game-select">Game</label>
          <select id="game-select" v-model="selectedGameId" @change="loadGamePlayerStats">
            <option
              v-for="game in playedGames"
              :key="game.id || game.date + game.opponent"
              :value="game.id"
            >
              {{ formatGameDate(game.date) }} • {{ game.home ? 'vs' : '@' }} {{ game.opponent }}
            </option>
          </select>
        </div>
        <p v-if="gameStatsLoading">Loading game player stats...</p>
        <p v-else-if="gameStatsMessage" class="game-stats-note">{{ gameStatsMessage }}</p>
        <table class="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Position</th>
              <th v-for="stat in playerStats" :key="stat">{{ stat.toUpperCase() }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="player in displayPlayers" :key="player.name">
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
          <div class="game" v-for="game in playedGamesWithRecord" :key="game.date + game.opponent">
            <div class="game-meta">
              <span class="game-date">{{ formatGameDate(game.date) }}</span>
              <strong>{{ game.home ? 'Home' : 'Away' }}</strong>
              <span>vs {{ game.opponent }}</span>
            </div>
            <div class="game-score">
              <span>Final: {{ game.score || '-' }}</span>
              <span class="game-record" v-if="game.recordAfter">Record: {{ game.recordAfter }}</span>
            </div>
          </div>
          <p v-if="playedGames.length === 0">No completed games available.</p>
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
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const team = ref(null)
const loading = ref(true)
const error = ref('')
const apiUrl = process.env.VUE_APP_API_URL || '/api'
const selectedGameId = ref('')
const gameStatsPlayers = ref([])
const gameStatsLoading = ref(false)
const gameStatsMessage = ref('')

const displayPlayers = computed(() => {
  if (gameStatsPlayers.value.length > 0) {
    return gameStatsPlayers.value
  }
  return team.value?.players || []
})

const playerStats = computed(() => {
  if (displayPlayers.value.length === 0) {
    return []
  }

  const preferredOrder = [
    'points',
    'rebounds',
    'assists',
    'goals',
    'home_runs',
    'rbi',
    'hits',
    'batting_avg',
    'appearances',
  ]

  const discovered = new Set()
  for (const player of displayPlayers.value) {
    const stats = player?.stats || {}
    for (const statKey of Object.keys(stats)) {
      discovered.add(statKey)
    }
  }

  const ordered = preferredOrder.filter((key) => discovered.has(key))
  const extra = [...discovered].filter((key) => !preferredOrder.includes(key)).sort()
  return [...ordered, ...extra]
})

const playedGames = computed(() => {
  if (!team.value || !Array.isArray(team.value.games)) {
    return []
  }

  return [...team.value.games]
    .filter((game) => game?.status === 'played')
    .sort((first, second) => {
      const firstDate = Date.parse(first?.date || '')
      const secondDate = Date.parse(second?.date || '')
      return (Number.isFinite(secondDate) ? secondDate : 0) - (Number.isFinite(firstDate) ? firstDate : 0)
    })
})

const playedGamesWithRecord = computed(() => {
  if (playedGames.value.length === 0) {
    return []
  }

  const chronological = [...playedGames.value].reverse()
  let wins = 0
  let losses = 0

  const withRecord = chronological.map((game) => {
    const score = String(game?.score || '')
    const [homeRaw, awayRaw] = score.split('-').map((value) => Number.parseInt(value, 10))
    let recordAfter = ''

    if (Number.isFinite(homeRaw) && Number.isFinite(awayRaw)) {
      const teamScore = game.home ? homeRaw : awayRaw
      const opponentScore = game.home ? awayRaw : homeRaw
      if (teamScore > opponentScore) {
        wins += 1
      } else if (teamScore < opponentScore) {
        losses += 1
      }
      recordAfter = `${wins}-${losses}`
    }

    return {
      ...game,
      recordAfter,
    }
  })

  return withRecord.reverse()
})

const teamRecord = computed(() => {
  if (playedGamesWithRecord.value.length === 0) {
    return ''
  }
  return playedGamesWithRecord.value[0].recordAfter || ''
})

const formatGameDate = (rawDate) => {
  const value = String(rawDate || '').trim()
  if (!value) {
    return 'Date TBD'
  }

  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(parsed)
}

const loadTeam = async () => {
  loading.value = true
  error.value = ''
  team.value = null
  selectedGameId.value = ''
  gameStatsPlayers.value = []
  gameStatsMessage.value = ''

  try {
    const league = route.params.league
    const teamId = route.params.id
    const response = await fetch(`${apiUrl}/leagues/${league}/teams/${teamId}`)
    if (!response.ok) {
      const message = await response.text()
      throw new Error(message || `API error: ${response.status}`)
    }
    team.value = await response.json()
    if (playedGames.value.length > 0) {
      selectedGameId.value = playedGames.value[0].id || ''
      await loadGamePlayerStats()
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unknown error'
  } finally {
    loading.value = false
  }
}

const loadGamePlayerStats = async () => {
  if (!selectedGameId.value) {
    gameStatsPlayers.value = []
    gameStatsMessage.value = 'No game id available for selected game. Showing team-level stats.'
    return
  }

  gameStatsLoading.value = true
  gameStatsMessage.value = ''
  gameStatsPlayers.value = []

  try {
    const league = route.params.league
    const teamId = route.params.id
    const response = await fetch(`${apiUrl}/leagues/${league}/teams/${teamId}/games/${selectedGameId.value}/players`)
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`)
    }

    const data = await response.json()
    gameStatsPlayers.value = data.players || []
    if (gameStatsPlayers.value.length === 0) {
      gameStatsMessage.value = 'No per-game player box score data for this game from current source. Showing team-level stats.'
    }
  } catch {
    gameStatsPlayers.value = []
    gameStatsMessage.value = 'Unable to load per-game player stats. Showing team-level stats.'
  } finally {
    gameStatsLoading.value = false
  }
}

watch(
  () => [route.params.league, route.params.id],
  () => {
    loadTeam()
  },
  { immediate: true },
)
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

.team-header-logo {
  width: 28px;
  height: 28px;
  object-fit: contain;
  vertical-align: middle;
  margin-right: 8px;
}

.record {
  font-size: 14px;
  color: #111827;
  margin-left: 8px;
  font-weight: 700;
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

.game-select-wrap {
  margin: 8px 0 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.game-select-wrap label {
  font-weight: 600;
}

.game-select-wrap select {
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid #d1d5db;
  font-size: 14px;
}

.game-stats-note {
  color: #6b7280;
  margin: 8px 0;
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

.game-date {
  margin-top: 0;
  font-size: 12px;
  color: #4b5563;
}

.game-score {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  font-weight: 600;
}

.game-record {
  font-size: 12px;
  color: #4b5563;
  font-weight: 500;
}
</style>
