import { motion } from "framer-motion"
import { Sidebar } from "./Sidebar"
import { Header } from "./Header"
import { useAppStore } from "../../store/useAppStore"

interface Props { children: React.ReactNode }

export function Layout({ children }: Props) {
  const { sidebarOpen } = useAppStore()

  return (
    <div className="min-h-screen bg-bg flex">
      <Sidebar />

      <motion.div
        className="flex-1 flex flex-col min-h-screen"
        animate={{ paddingLeft: sidebarOpen ? 220 : 60 }}
        transition={{ duration: 0.25, ease: "easeInOut" }}
      >
        <Header />
        <main className="flex-1 pt-[60px] overflow-auto">
          <motion.div
            className="p-4 md:p-6 max-w-[1600px] mx-auto w-full"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            {children}
          </motion.div>
        </main>
      </motion.div>
    </div>
  )
}
