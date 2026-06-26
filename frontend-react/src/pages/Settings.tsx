import { motion } from "framer-motion"
import { Settings as SettingsIcon, Monitor, Globe, Zap, Brain, Trash2, RefreshCw } from "lucide-react"
import { useAppStore } from "../store/useAppStore"
import { useMutation } from "@tanstack/react-query"
import { triggerLoadFromDB, triggerLoadFactors, triggerTrainFormModel } from "../api/endpoints"
import { Badge } from "../components/ui/Badge"
import type { Language, ModelType } from "../types"
import clsx from "clsx"

const SIM_OPTIONS = [1_000, 10_000, 100_000, 500_000, 1_000_000]
const MODELS: { value: ModelType; label: string }[] = [
  { value: "hybrid",      label: "Hybrid" },
  { value: "elo",         label: "Elo" },
  { value: "dixon_coles", label: "Dixon-Coles" },
  { value: "klement",     label: "Klement" },
]
const LANGS: { value: Language; label: string; flag: string }[] = [
  { value: "es", label: "Español",   flag: "🇪🇸" },
  { value: "en", label: "English",   flag: "🇬🇧" },
  { value: "pt", label: "Português", flag: "🇧🇷" },
]

export function Settings() {
  const { settings, updateSettings, clearHistory } = useAppStore()

  const { mutate: loadDB, isPending: loadingDB, data: dbResult, error: dbError } = useMutation({ mutationFn: triggerLoadFromDB })
  const { mutate: loadFactors, isPending: loadingFac } = useMutation({ mutationFn: triggerLoadFactors })
  const { mutate: trainForm, isPending: trainingForm } = useMutation({ mutationFn: triggerTrainFormModel })

  return (
    <div className="space-y-6 animate-fade-in max-w-2xl">
      {/* Header */}
      <div className="card border-muted/20">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-muted/10 border border-muted/20 flex items-center justify-center">
            <SettingsIcon className="w-5 h-5 text-muted" />
          </div>
          <div>
            <h2 className="font-display text-2xl tracking-wider text-text">CONFIGURACIÓN</h2>
            <p className="text-xs text-muted">Personaliza la plataforma Football AI Analytics</p>
          </div>
        </div>
      </div>

      {/* Theme */}
      <div className="card space-y-4">
        <div className="flex items-center gap-2">
          <Monitor className="w-4 h-4 text-cyan" />
          <h3 className="section-title text-lg">APARIENCIA</h3>
        </div>
        <div className="grid grid-cols-2 gap-3">
          {(["dark", "light"] as const).map(t => (
            <button
              key={t}
              onClick={() => updateSettings({ theme: t })}
              className={clsx(
                "p-4 rounded-xl border flex flex-col items-center gap-2 transition-all",
                settings.theme === t ? "border-cyan/40 bg-cyan/10" : "border-border hover:bg-white/5"
              )}
            >
              <span className="text-2xl">{t === "dark" ? "🌙" : "☀️"}</span>
              <span className={clsx("text-sm font-medium", settings.theme === t ? "text-cyan" : "text-muted")}>
                {t === "dark" ? "Oscuro" : "Claro"}
              </span>
              {settings.theme === t && <Badge variant="cyan">Activo</Badge>}
            </button>
          ))}
        </div>
        <div className="flex items-center justify-between py-3 border-t border-border">
          <div>
            <p className="text-sm text-text">Animaciones</p>
            <p className="text-xs text-muted">Transiciones y efectos visuales</p>
          </div>
          <button
            onClick={() => updateSettings({ animations: !settings.animations })}
            className={clsx(
              "w-12 h-6 rounded-full transition-all relative",
              settings.animations ? "bg-cyan" : "bg-border"
            )}
          >
            <motion.span
              animate={{ x: settings.animations ? 24 : 2 }}
              className="absolute top-1 w-4 h-4 rounded-full bg-white shadow"
            />
          </button>
        </div>
      </div>

      {/* Language */}
      <div className="card space-y-4">
        <div className="flex items-center gap-2">
          <Globe className="w-4 h-4 text-cyan" />
          <h3 className="section-title text-lg">IDIOMA</h3>
        </div>
        <div className="grid grid-cols-3 gap-3">
          {LANGS.map(l => (
            <button
              key={l.value}
              onClick={() => updateSettings({ language: l.value })}
              className={clsx(
                "p-3 rounded-xl border flex flex-col items-center gap-1.5 transition-all",
                settings.language === l.value ? "border-cyan/40 bg-cyan/10" : "border-border hover:bg-white/5"
              )}
            >
              <span className="text-xl">{l.flag}</span>
              <span className={clsx("text-xs font-medium", settings.language === l.value ? "text-cyan" : "text-muted")}>
                {l.label}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Default model */}
      <div className="card space-y-4">
        <div className="flex items-center gap-2">
          <Brain className="w-4 h-4 text-cyan" />
          <h3 className="section-title text-lg">MODELO FAVORITO</h3>
        </div>
        <div className="grid grid-cols-2 gap-3">
          {MODELS.map(m => (
            <button
              key={m.value}
              onClick={() => updateSettings({ default_model: m.value })}
              className={clsx(
                "p-3 rounded-xl border text-left transition-all",
                settings.default_model === m.value ? "border-cyan/40 bg-cyan/10" : "border-border hover:bg-white/5"
              )}
            >
              <p className={clsx("text-sm font-medium", settings.default_model === m.value ? "text-cyan" : "text-text")}>
                {m.label}
              </p>
              {settings.default_model === m.value && <Badge variant="cyan" size="sm">Predeterminado</Badge>}
            </button>
          ))}
        </div>
      </div>

      {/* Simulations */}
      <div className="card space-y-4">
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-cyan" />
          <h3 className="section-title text-lg">SIMULACIONES</h3>
        </div>
        <div>
          <p className="text-xs text-muted mb-3">Cantidad de simulaciones por defecto</p>
          <div className="grid grid-cols-3 md:grid-cols-5 gap-2">
            {SIM_OPTIONS.map(n => (
              <button
                key={n}
                onClick={() => updateSettings({ default_sims: n })}
                className={clsx(
                  "py-2 px-3 rounded-lg border text-sm font-display tracking-wider transition-all",
                  settings.default_sims === n ? "border-amber/40 bg-amber/10 text-amber" : "border-border text-muted hover:text-text"
                )}
              >
                {n >= 1_000_000 ? "1M" : n >= 100_000 ? `${n / 1000}K` : `${n / 1000}K`}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="card space-y-4">
        <h3 className="section-title text-lg">ACCIONES DEL SISTEMA</h3>

        <div className="space-y-3">
          <div className="flex items-center justify-between py-3 border-b border-border">
            <div>
              <p className="text-sm text-text">Cargar datos desde DB</p>
              <p className="text-xs text-muted">Rebuild Elo + Dixon-Coles desde partidos almacenados</p>
            </div>
            <button
              onClick={() => loadDB()}
              disabled={loadingDB}
              className="btn-ghost flex items-center gap-2 text-xs"
            >
              {loadingDB ? <RefreshCw className="w-3 h-3 animate-spin" /> : null}
              {loadingDB ? "Cargando..." : "Cargar DB"}
            </button>
          </div>
          {dbResult && <p className="text-xs text-emerald">✓ {dbResult.matches} partidos, {dbResult.teams} equipos cargados</p>}
          {dbError && <p className="text-xs text-scarlet">{String(dbError)}</p>}

          <div className="flex items-center justify-between py-3 border-b border-border">
            <div>
              <p className="text-sm text-text">Cargar factores Klement</p>
              <p className="text-xs text-muted">PIB, población, FIFA pts por equipo</p>
            </div>
            <button onClick={() => loadFactors()} disabled={loadingFac} className="btn-ghost text-xs flex items-center gap-2">
              {loadingFac && <RefreshCw className="w-3 h-3 animate-spin" />}
              {loadingFac ? "Cargando..." : "Cargar Klement"}
            </button>
          </div>

          <div className="flex items-center justify-between py-3 border-b border-border">
            <div>
              <p className="text-sm text-text">Entrenar modelo XGBoost</p>
              <p className="text-xs text-muted">Walk-forward sobre partidos históricos</p>
            </div>
            <button onClick={() => trainForm()} disabled={trainingForm} className="btn-ghost text-xs flex items-center gap-2">
              {trainingForm && <RefreshCw className="w-3 h-3 animate-spin" />}
              {trainingForm ? "Entrenando..." : "Entrenar XGB"}
            </button>
          </div>

          <div className="flex items-center justify-between py-3">
            <div>
              <p className="text-sm text-text">Limpiar historial local</p>
              <p className="text-xs text-muted">Elimina predicciones y simulaciones guardadas</p>
            </div>
            <button
              onClick={() => { if (confirm("¿Limpiar historial?")) clearHistory() }}
              className="btn-ghost text-xs text-scarlet border-scarlet/20 hover:border-scarlet/50 flex items-center gap-2"
            >
              <Trash2 className="w-3 h-3" />
              Limpiar
            </button>
          </div>
        </div>
      </div>

      {/* Version */}
      <div className="text-center text-xs text-muted/40 py-2">
        Football AI Analytics v2.0 · FastAPI + React + TypeScript
      </div>
    </div>
  )
}
