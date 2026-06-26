import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { AnimatePresence } from "framer-motion"
import { Layout } from "./components/layout/Layout"
import { useAppStore } from "./store/useAppStore"

import { Dashboard }          from "./pages/Dashboard"
import { MatchPrediction }     from "./pages/MatchPrediction"
import { TournamentSimulator } from "./pages/TournamentSimulator"
import { Probabilities }       from "./pages/Probabilities"
import { EloRankings }         from "./pages/EloRankings"
import { AIAnalysis }          from "./pages/AIAnalysis"
import { AIChat }              from "./pages/AIChat"
import { Laboratory }          from "./pages/Laboratory"
import { Players }             from "./pages/Players"
import { Teams }               from "./pages/Teams"
import { Compare }             from "./pages/Compare"
import { Statistics }          from "./pages/Statistics"
import { Calendar }            from "./pages/Calendar"
import { Transfers }           from "./pages/Transfers"
import { History }             from "./pages/History"
import { Settings }            from "./pages/Settings"

const qc = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
})

function PageRouter() {
  const { currentPage } = useAppStore()

  const pages: Record<string, React.ReactNode> = {
    dashboard:     <Dashboard />,
    prediction:    <MatchPrediction />,
    simulator:     <TournamentSimulator />,
    probabilities: <Probabilities />,
    elo:           <EloRankings />,
    "ai-analysis": <AIAnalysis />,
    "ai-chat":     <AIChat />,
    models:        <Laboratory />,
    laboratory:    <Laboratory />,
    players:       <Players />,
    teams:         <Teams />,
    compare:       <Compare />,
    statistics:    <Statistics />,
    calendar:      <Calendar />,
    transfers:     <Transfers />,
    history:       <History />,
    settings:      <Settings />,
  }

  return (
    <AnimatePresence mode="wait">
      <div key={currentPage}>
        {pages[currentPage] ?? <Dashboard />}
      </div>
    </AnimatePresence>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <Layout>
        <PageRouter />
      </Layout>
    </QueryClientProvider>
  )
}
