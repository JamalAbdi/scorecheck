<template>
	<section class="home">
		<div class="today-games">
			<h3>Today's Games</h3>
			<p v-if="loadingTodayGames">Loading games...</p>
			<p v-else-if="todayGamesError" class="today-games-error">{{ todayGamesError }}</p>
			<div v-else>
				<p v-if="hasNoTodayGames && hasAnyYesterdayGames" class="today-empty">
					No games today. Showing yesterday below.
				</p>
				<div class="today-leagues">
					<div v-for="league in sortedTodayLeagues" :key="`today-${league.id}`" class="today-league">
						<h4>{{ league.name }}</h4>
						<div v-if="league.games.length === 0" class="today-empty">No games today.</div>
						<div v-else class="today-list">
							<div v-for="game in league.games" :key="game.id || `${league.id}-${game.home_team}-${game.away_team}`" class="today-game">
								<div class="today-teams">
									<div class="team-row">
										<router-link :to="teamRoute(league.id, game.away_team)" class="today-team-link">
											<img v-if="game.away_logo" :src="game.away_logo" :alt="`${game.away_team} logo`" class="team-logo" />
											<div class="team-text">
												<strong>{{ displayTeamName(game.away_team) }}</strong>
												<span class="team-record">({{ game.away_record || '-' }})</span>
											</div>
										</router-link>
										<span class="team-score">{{ displayTeamScore(game, 'away') }}</span>
									</div>
									<div class="team-row">
										<router-link :to="teamRoute(league.id, game.home_team)" class="today-team-link">
											<img v-if="game.home_logo" :src="game.home_logo" :alt="`${game.home_team} logo`" class="team-logo" />
											<div class="team-text">
												<strong>{{ displayTeamName(game.home_team) }}</strong>
												<span class="team-record">({{ game.home_record || '-' }})</span>
											</div>
										</router-link>
										<span class="team-score">{{ displayTeamScore(game, 'home') }}</span>
									</div>
								</div>
								<div class="today-status">
									<span class="today-label">{{ gameStateLabel(game) }}</span>
									<span v-if="!isCompletedStatus(game?.status)" class="today-time">{{ formatGameTime(game) }}</span>
								</div>
							</div>
						</div>
					</div>
				</div>

				<div class="yesterday-section">
					<div class="section-heading-row">
						<h3 class="yesterday-heading">Yesterday's Games</h3>
						<span class="date-bubble">Yesterday</span>
					</div>
					<div class="today-leagues">
						<div v-for="league in sortedYesterdayLeagues" :key="`yesterday-${league.id}`" class="today-league">
							<h4>{{ league.name }}</h4>
							<div v-if="league.games.length === 0" class="today-empty">No games yesterday.</div>
							<div v-else class="today-list">
								<div v-for="game in league.games" :key="game.id || `${league.id}-${game.home_team}-${game.away_team}`" class="today-game">
									<div class="today-teams">
										<div class="team-row">
											<router-link :to="teamRoute(league.id, game.away_team)" class="today-team-link">
												<img v-if="game.away_logo" :src="game.away_logo" :alt="`${game.away_team} logo`" class="team-logo" />
												<div class="team-text">
													<strong>{{ displayTeamName(game.away_team) }}</strong>
													<span class="team-record">({{ game.away_record || '-' }})</span>
												</div>
											</router-link>
											<span class="team-score">{{ displayTeamScore(game, 'away') }}</span>
										</div>
										<div class="team-row">
											<router-link :to="teamRoute(league.id, game.home_team)" class="today-team-link">
												<img v-if="game.home_logo" :src="game.home_logo" :alt="`${game.home_team} logo`" class="team-logo" />
												<div class="team-text">
													<strong>{{ displayTeamName(game.home_team) }}</strong>
													<span class="team-record">({{ game.home_record || '-' }})</span>
												</div>
											</router-link>
											<span class="team-score">{{ displayTeamScore(game, 'home') }}</span>
										</div>
									</div>
									<div class="today-status">
										<span class="today-label">{{ gameStateLabel(game) }}</span>
										<span class="today-date">{{ formatGameDate(game) }}</span>
										<span class="today-date">{{ formatGameDate(game) }}</span>
										<span v-if="!isCompletedStatus(game?.status)" class="today-time">{{ formatGameTime(game) }}</span>
									</div>
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>
	</section>
</template>

<script>
export default {
	name: 'HomeView',
}
</script>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'

const apiUrl = process.env.VUE_APP_API_URL || '/api'
const loadingTodayGames = ref(true)
const todayGamesError = ref('')
const todayGamesPayload = ref({})
const teamsByLeague = ref({})
let todayGamesIntervalId = null

const normalizeLeagues = (value) => {
	if (!Array.isArray(value)) {
		return []
	}
	return value
}

const todayLeagues = computed(() => {
	const payload = todayGamesPayload.value || {}
	if (payload.today && Array.isArray(payload.today.leagues)) {
		return normalizeLeagues(payload.today.leagues)
	}
	return normalizeLeagues(payload.leagues)
})

const yesterdayLeagues = computed(() => {
	const payload = todayGamesPayload.value || {}
	if (payload.yesterday && Array.isArray(payload.yesterday.leagues)) {
		return normalizeLeagues(payload.yesterday.leagues)
	}
	return []
})

const totalGames = (leagues) => leagues
	.reduce((count, league) => count + (Array.isArray(league.games) ? league.games.length : 0), 0)

const hasNoTodayGames = computed(() => totalGames(todayLeagues.value) === 0)
const hasAnyYesterdayGames = computed(() => totalGames(yesterdayLeagues.value) > 0)

const formatGameTime = (game) => {
	const rawStart = game?.start_time
	if (!rawStart) {
		return 'TBD'
	}

	const parsedDate = new Date(rawStart)
	if (Number.isNaN(parsedDate.getTime())) {
		return 'TBD'
	}

	return new Intl.DateTimeFormat(undefined, {
		hour: 'numeric',
		minute: '2-digit',
	}).format(parsedDate)
}

const formatGameDate = (game) => {
	const rawStart = game?.start_time
	if (!rawStart) {
		return 'Date TBD'
	}

	const parsedDate = new Date(rawStart)
	if (Number.isNaN(parsedDate.getTime())) {
		return 'Date TBD'
	}

	return new Intl.DateTimeFormat(undefined, {
		month: 'short',
		day: 'numeric',
	}).format(parsedDate)
}

const isCompletedStatus = (status) => {
	const value = String(status || '').toLowerCase()
	return value.includes('final') || value.includes('complete') || value.includes('completed')
}

const isLiveStatus = (status) => {
	const value = String(status || '').toLowerCase()
	return (
		value.includes('in progress')
		|| value.includes('live')
		|| value.includes('qtr')
		|| value.includes('quarter')
		|| value.includes('period')
		|| value.includes('inning')
	)
}

const formatLiveStatus = (status) => String(status || '')
	.replace(/\b(\d+)(?:st|nd|rd|th)\s+quarter\b/gi, 'Q$1')
	.replace(/\bquarter\b/gi, 'Q')
	.replace(/\s+/g, ' ')
	.trim()

const gameStateLabel = (game) => {
	if (isCompletedStatus(game?.status)) {
		return 'Complete'
	}
	if (isLiveStatus(game?.status)) {
		return formatLiveStatus(game?.status) || 'Live'
	}
	return 'Scheduled'
}

const gameDisplayRank = (game) => {
	if (isLiveStatus(game?.status)) {
		return 0
	}
	if (isCompletedStatus(game?.status)) {
		return 2
	}
	return 1
}

const sortGamesForDisplay = (games) => {
	if (!Array.isArray(games)) {
		return []
	}

	return games
		.map((game, index) => ({ game, index }))
		.sort((a, b) => {
			const rankDiff = gameDisplayRank(a.game) - gameDisplayRank(b.game)
			if (rankDiff !== 0) {
				return rankDiff
			}
			return a.index - b.index
		})
		.map(({ game }) => game)
}

const sortLeaguesForDisplay = (leagues) => leagues.map((league) => ({
	...league,
	games: sortGamesForDisplay(league.games),
}))

const sortedTodayLeagues = computed(() => sortLeaguesForDisplay(todayLeagues.value))
const sortedYesterdayLeagues = computed(() => sortLeaguesForDisplay(yesterdayLeagues.value))

const displayTeamScore = (game, side) => {
	if (!isCompletedStatus(game?.status) && !isLiveStatus(game?.status)) {
		return ''
	}

	if (side === 'away') {
		return String(game?.away_score ?? '').trim()
	}

	return String(game?.home_score ?? '').trim()
}

const slugify = (value) => String(value || '')
	.toLowerCase()
	.replace(/[^a-z0-9]+/g, '-')
	.replace(/^-+|-+$/g, '')

const buildTeamLookup = (teams) => {
	const lookup = {}
	for (const team of teams || []) {
		const name = String(team?.name || '').toLowerCase().trim()
		const id = String(team?.id || '').trim()
		if (name && id) {
			lookup[name] = id
		}
	}
	return lookup
}

const teamRoute = (leagueId, teamName) => {
	const key = String(teamName || '').toLowerCase().trim()
	const mappedId = teamsByLeague.value?.[leagueId]?.[key]
	const fallbackId = slugify(teamName)
	return `/teams/${leagueId}/${mappedId || fallbackId}`
}

const displayTeamName = (teamName) => {
	const normalized = String(teamName || '').trim().toLowerCase()
	if (normalized === 'oklahoma city thunder') {
		return 'OKC Thunder'
	}
	if (normalized === 'oklahoma city') {
		return 'OKC'
	}
	return teamName
}

const loadLeagueTeams = async () => {
	const leagues = ['nba', 'nhl', 'mlb']
	const next = {}

	for (const leagueId of leagues) {
		try {
			const response = await fetch(`${apiUrl}/leagues/${leagueId}/teams`)
			if (!response.ok) {
				next[leagueId] = {}
				continue
			}
			const data = await response.json()
			next[leagueId] = buildTeamLookup(data.teams || [])
		} catch {
			next[leagueId] = {}
		}
	}

	teamsByLeague.value = next
}

const loadTodayGames = async ({ silent = false } = {}) => {
	if (!silent) {
		loadingTodayGames.value = true
		todayGamesError.value = ''
	}

	try {
		const response = await fetch(`${apiUrl}/games/today?t=${Date.now()}`, {
			cache: 'no-store',
		})
		if (!response.ok) {
			throw new Error(`API error: ${response.status}`)
		}
		const data = await response.json()
		todayGamesPayload.value = data || {}
	} catch {
		todayGamesError.value = 'Unable to load games right now.'
		todayGamesPayload.value = {}
	} finally {
		if (!silent) {
			loadingTodayGames.value = false
		}
	}
}

onMounted(async () => {
	await Promise.all([loadTodayGames(), loadLeagueTeams()])
	todayGamesIntervalId = window.setInterval(() => {
		loadTodayGames({ silent: true })
	}, 30000)
})

onUnmounted(() => {
	if (todayGamesIntervalId) {
		window.clearInterval(todayGamesIntervalId)
		todayGamesIntervalId = null
	}
})
</script>

<style scoped>
.home {
	background: #fff;
	border-radius: 16px;
	padding: 24px;
	box-shadow: 0 10px 20px rgba(15, 23, 42, 0.08);
}

.home p {
	margin: 0;
	color: #6b7280;
}

.today-games h3 {
	margin: 0 0 10px;
}

.section-heading-row {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 10px;
	margin-bottom: 10px;
}

.yesterday-heading {
	margin: 0;
}

.date-bubble {
	display: inline-flex;
	align-items: center;
	padding: 4px 10px;
	border-radius: 999px;
	border: 1px solid #dbe3f0;
	background: #fff;
	color: #0f172a;
	font-size: 12px;
	font-weight: 600;
}

.yesterday-section {
	margin-top: 28px;
	padding: 16px;
	border: 1px solid #e5e7eb;
	border-radius: 14px;
	background: #f9fafb;
}

.today-games-error {
	color: #b91c1c;
}

.today-leagues {
	display: grid;
	gap: 16px;
}

.today-league h4 {
	margin: 0 0 8px;
}

.today-empty {
	color: #6b7280;
	font-size: 14px;
}

.today-list {
	display: grid;
	grid-template-columns: repeat(2, minmax(0, 1fr));
	gap: 10px;
}

.today-game {
	display: grid;
	grid-template-columns: minmax(0, 1fr) 96px;
	align-items: start;
	gap: 5px;
	padding: 10px 12px;
	border: 1px solid #e5e7eb;
	border-radius: 10px;
}

.today-teams {
	display: flex;
	flex-direction: column;
	gap: 8px;
	flex: 1;
	min-width: 0;
}

.team-row {
	display: grid;
	grid-template-columns: minmax(0, 1fr) 36px;
	align-items: flex-start;
	gap: 18px;
	width: 100%;
}

.today-team-link {
	display: grid;
	grid-template-columns: 18px minmax(0, 1fr);
	column-gap: 6px;
	row-gap: 1px;
	align-items: center;
	text-decoration: none;
	color: #111827;
	min-width: 0;
}

.team-text {
	display: flex;
	flex-direction: column;
	min-width: 0;
}

.team-text strong {
	font-size: 13px;
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.team-record {
	font-size: 11px;
	color: #6b7280;
}

.team-score {
	font-size: 18px;
	font-weight: 700;
	color: #111827;
	width: 36px;
	text-align: right;
	justify-self: end;
	font-variant-numeric: tabular-nums;
	line-height: 1;
	padding-top: 1px;
}

.today-team-link:hover {
	text-decoration: underline;
}

.team-logo {
	width: 18px;
	height: 18px;
	object-fit: contain;
}

.today-status {
	text-align: right;
	font-size: 13px;
	color: #4b5563;
	display: flex;
	flex-direction: column;
	align-items: flex-end;
	gap: 2px;
	width: 96px;
}

.today-label {
	font-weight: 600;
	color: #111827;
}

.today-time {
	font-size: 12px;
}

.today-date {
	font-size: 12px;
	color: #6b7280;
}

@media (max-width: 900px) {
	.today-list {
		grid-template-columns: 1fr;
	}

	.today-game {
		grid-template-columns: minmax(0, 1fr);
	}

	.today-status {
		width: auto;
	}
}
</style>
