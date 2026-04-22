/**
 * EstatPage — /staff/estat
 *
 * Visual system-health dashboard. Everything staff wants to know at
 * a glance:
 *   - BD inventory (artistes/albums/cançons counts with state pills)
 *   - Whisper LID coverage progress bar + rate
 *   - Ranking state (weekly + provisional)
 *   - Cron health matrix (colour-coded per last run)
 *   - ML model summary + feature importance bar chart
 *   - Community queues (feedback/propostes/sol·licituds)
 *
 * Data comes from a single GET /api/v1/staff/estat/ call — no live
 * polling (daily data doesn't change that fast), but the page
 * refreshes every 60 s in case staff leaves it open.
 */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../lib/api'
import { PageHeader, Pill, TableCard } from '../../components/staff/StaffTable'

// ── Small display helpers ────────────────────────────────────────────────

function BigNumber({ label, value, sub, tone = 'ink' }) {
  const tones = {
    ink:    'bg-white text-tq-ink',
    yellow: 'bg-tq-yellow text-tq-ink',
    green:  'bg-emerald-100 text-emerald-900',
    red:    'bg-red-100 text-red-900',
    gray:   'bg-gray-100 text-gray-800',
  }
  return (
    <div className={`rounded-lg p-4 ${tones[tone] || tones.ink}`}>
      <p className="text-[10px] uppercase tracking-widest opacity-70">{label}</p>
      <p className="text-3xl font-bold font-display tabular-nums mt-1">
        {typeof value === 'number' ? value.toLocaleString('ca') : value ?? '—'}
      </p>
      {sub && <p className="text-[11px] opacity-60 mt-0.5">{sub}</p>}
    </div>
  )
}

function StackedBar({ segments, total }) {
  // segments = [{label, value, color}]. Normalises by total.
  if (!total) return null
  return (
    <div className="w-full">
      <div className="flex h-6 rounded-md overflow-hidden border border-black/5">
        {segments.map(s => {
          const pct = (s.value / total) * 100
          if (pct <= 0) return null
          return (
            <div
              key={s.label}
              style={{ width: `${pct}%`, background: s.color }}
              title={`${s.label}: ${s.value.toLocaleString('ca')} (${pct.toFixed(1)}%)`}
            />
          )
        })}
      </div>
      <div className="flex flex-wrap gap-3 mt-2 text-[11px]">
        {segments.map(s => (
          <span key={s.label} className="inline-flex items-center gap-1">
            <span
              className="inline-block w-2.5 h-2.5 rounded-sm"
              style={{ background: s.color }}
            />
            <span className="font-semibold">{s.label}</span>
            <span className="opacity-60">
              {s.value.toLocaleString('ca')} ({((s.value / total) * 100).toFixed(1)}%)
            </span>
          </span>
        ))}
      </div>
    </div>
  )
}

function HorizontalBars({ items, max, formatValue }) {
  return (
    <ul className="space-y-1.5">
      {items.map(item => {
        const pct = max ? (item.value / max) * 100 : 0
        return (
          <li key={item.name} className="flex items-center gap-3 text-xs">
            <span className="w-48 truncate font-mono text-tq-ink/80" title={item.name}>
              {item.name}
            </span>
            <div className="flex-1 h-4 bg-tq-ink/5 rounded overflow-hidden">
              <div
                className="h-full bg-tq-yellow"
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="w-14 text-right tabular-nums">
              {formatValue ? formatValue(item.value) : item.value}
            </span>
          </li>
        )
      })}
    </ul>
  )
}

function CronStatus({ cron }) {
  const ok = cron.status === 'OK'
  const tone = ok ? 'green' : 'red'
  const when = cron.last_run ? cron.last_run.slice(0, 16).replace('T', ' ') : '—'
  const attempts = cron.attempts && cron.attempts !== '1' ? ` · ${cron.attempts}×` : ''
  return (
    <li className="flex items-center gap-3 text-xs py-1.5 border-t border-black/5 first:border-t-0">
      <Pill tone={tone}>{cron.status || '—'}</Pill>
      <span className="font-mono font-semibold text-tq-ink/80 flex-1 truncate">
        {cron.name}
      </span>
      <span className="opacity-60 whitespace-nowrap">
        {when}
        {attempts}
      </span>
    </li>
  )
}

// ── Main ─────────────────────────────────────────────────────────────────

export default function EstatPage() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    function load() {
      api.get('/staff/estat/').then(setData).catch(e => setError(e.message))
    }
    load()
    const t = setInterval(load, 60_000)
    return () => clearInterval(t)
  }, [])

  if (error) {
    return (
      <section>
        <PageHeader title="Estat del sistema" />
        <p className="text-sm text-red-300">Error: {error}</p>
      </section>
    )
  }
  if (!data) {
    return (
      <section>
        <PageHeader title="Estat del sistema" subtitle="Carregant…" />
      </section>
    )
  }

  const { bd, whisper, ranking, senyal, comunitat, crons, ml, flux } = data

  // Biggest importance for scaling bars.
  const maxImp = ml?.importances?.[0]?.value || 1
  const topImportances = (ml?.importances || []).slice(0, 20)

  // Classified counts for the ML class bar.
  const clsA = ml?.classe_distribution?.A || 0
  const clsB = ml?.classe_distribution?.B || 0
  const clsC = ml?.classe_distribution?.C || 0
  const clsNone = ml?.classe_distribution?.none || 0
  const clsTotal = clsA + clsB + clsC + clsNone

  const whisperTotal = whisper.ca + whisper.no_ca + whisper.pendent

  return (
    <section className="space-y-6">
      <PageHeader
        title="Estat del sistema"
        subtitle="Salut, dades i rendiment del pipeline en temps real"
      />

      {/* ─── Flux setmanal — la lectura més crítica a la part de dalt ─── */}
      {flux && (
        <section>
          <h2 className="text-sm uppercase tracking-widest text-white/60 mb-2">
            Flux de verificació
          </h2>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <BigNumber
              label="Entren / setmana"
              value={flux.intake_setmanal_robust}
              sub={
                flux.anomaly_days_excluded > 0
                  ? `robust · últims 7d: ${flux.intake_7d}`
                  : `últims 7d: ${flux.intake_7d}`
              }
              tone="yellow"
            />
            <BigNumber
              label="Caducaran en 7 dies"
              value={flux.caducaran_7d}
              sub={`${flux.caducaran_30d} en els propers 30d`}
              tone="gray"
            />
            <BigNumber
              label="Target setmanal"
              value={flux.target_verificacio_setmanal}
              sub="Per no acumular backlog"
              tone={
                flux.target_verificacio_setmanal === 0
                  ? 'green'
                  : flux.target_verificacio_setmanal > 200
                  ? 'red'
                  : 'yellow'
              }
            />
            <BigNumber
              label="Backlog actual"
              value={flux.backlog_no_verificades}
              sub="Cançons no verificades"
              tone={flux.backlog_no_verificades > 5000 ? 'red' : 'ink'}
            />
          </div>
          <div className="mt-3 bg-white text-tq-ink rounded-lg p-4">
            <div className="flex items-baseline gap-3 mb-2">
              <p className="text-[11px] uppercase tracking-widest opacity-60">
                Entrades per setmana (últimes 4)
              </p>
              {flux.anomaly_days_excluded > 0 && (
                <p className="text-[11px] text-tq-yellow-deep">
                  ({flux.anomaly_days_excluded} dies d'anomalia exclosos del càlcul robust — llindar {flux.anomaly_day_threshold}/dia)
                </p>
              )}
            </div>
            <div className="flex items-end gap-2" style={{ height: 140 }}>
              {(() => {
                const MAX_BAR_PX = 100
                const maxN = Math.max(...flux.intake_per_setmana.map(x => x.n), 1)
                return flux.intake_per_setmana.map(w => {
                  const hPx = Math.max(2, Math.round((w.n / maxN) * MAX_BAR_PX))
                  return (
                  <div
                    key={w.label}
                    className="flex-1 flex flex-col items-center gap-1 min-w-0"
                  >
                    <div className="w-full flex items-end" style={{ height: MAX_BAR_PX }}>
                      <div
                        className="w-full rounded-t"
                        style={{
                          height: hPx,
                          background: 'linear-gradient(180deg, #facc15 0%, #ea580c 100%)',
                        }}
                        title={`${w.label}: ${w.n} entrades`}
                      />
                    </div>
                    <div className="text-[10px] tabular-nums opacity-70 truncate w-full text-center">
                      {w.n.toLocaleString('ca')}
                    </div>
                    <div className="text-[9px] opacity-50 truncate w-full text-center">
                      {w.label}
                    </div>
                  </div>
                  )
                })
              })()}
            </div>
            <p className="text-[11px] opacity-60 mt-3 leading-relaxed">
              <strong>Lectura:</strong> amb ~{flux.intake_setmanal_robust} entrades setmanals i{' '}
              {flux.caducaran_7d} caducitats en els propers 7 dies, cal verificar com a mínim{' '}
              <strong>{flux.target_verificacio_setmanal} cançons per setmana</strong> per
              no acumular més backlog. El backlog actual és de{' '}
              {flux.backlog_no_verificades.toLocaleString('ca')} cançons.
            </p>
          </div>
        </section>
      )}

      {/* ─── BD inventory ─── */}
      <section>
        <h2 className="text-sm uppercase tracking-widest text-white/60 mb-2">
          Base de dades
        </h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <BigNumber
            label="Cançons"
            value={bd.cancons.total}
            sub={`${bd.cancons.verificades.toLocaleString('ca')} verificades · ${bd.cancons.no_verificades_actives.toLocaleString('ca')} pendents`}
          />
          <BigNumber
            label="Artistes aprovats"
            value={bd.artistes.aprovats}
            sub={`${bd.artistes.pendents.toLocaleString('ca')} pendents de revisió`}
            tone="yellow"
          />
          <BigNumber
            label="Albums actius"
            value={bd.albums.actius}
            sub={bd.albums.descartats ? `${bd.albums.descartats} descartats` : undefined}
          />
          <BigNumber
            label="Senyal diari"
            value={senyal.total}
            sub={senyal.data_recent ? `últim: ${senyal.data_recent}` : undefined}
          />
        </div>

        <div className="mt-3 bg-white text-tq-ink rounded-lg p-4">
          <p className="text-[11px] uppercase tracking-widest opacity-60 mb-2">
            Distribució cançons
          </p>
          <StackedBar
            total={bd.cancons.total}
            segments={[
              { label: 'Verificades', value: bd.cancons.verificades, color: '#10b981' },
              { label: 'Pendents',    value: bd.cancons.no_verificades_actives, color: '#facc15' },
              { label: 'Inactives',   value: bd.cancons.inactives, color: '#9ca3af' },
            ]}
          />
        </div>
      </section>

      {/* ─── Whisper LID ─── */}
      <section>
        <h2 className="text-sm uppercase tracking-widest text-white/60 mb-2">
          Whisper LID (detecció d'idioma)
        </h2>
        <div className="bg-white text-tq-ink rounded-lg p-4">
          <p className="text-[11px] uppercase tracking-widest opacity-60 mb-2">
            Cobertura ({((whisperTotal - whisper.pendent) / whisperTotal * 100).toFixed(1)}% analitzat)
          </p>
          <StackedBar
            total={whisperTotal}
            segments={[
              { label: 'Català',       value: whisper.ca,      color: '#10b981' },
              { label: 'No-català',    value: whisper.no_ca,   color: '#ef4444' },
              { label: 'Pendent',      value: whisper.pendent, color: '#d1d5db' },
            ]}
          />
          <p className="text-[11px] opacity-60 mt-3">
            A ~700 cançons/nit el cron trigarà <strong>{Math.ceil(whisper.pendent / 700)} dies</strong> més a arribar al 100%.
          </p>
        </div>
      </section>

      {/* ─── Ranking + Comunitat ─── */}
      <section className="grid lg:grid-cols-2 gap-3">
        <div className="bg-white text-tq-ink rounded-lg p-4">
          <h3 className="text-sm font-semibold mb-3">Ranking</h3>
          <dl className="grid grid-cols-2 gap-y-1 text-xs">
            <dt className="opacity-60">Setmanes històriques</dt>
            <dd className="text-right font-semibold tabular-nums">{ranking.setmanes_historiques}</dd>
            <dt className="opacity-60">Entrades provisionals ara</dt>
            <dd className="text-right font-semibold tabular-nums">{ranking.provisional_ara}</dd>
            <dt className="opacity-60">Últim oficial</dt>
            <dd className="text-right font-semibold">{ranking.ultim_oficial || '—'}</dd>
          </dl>
        </div>

        <div className="bg-white text-tq-ink rounded-lg p-4">
          <h3 className="text-sm font-semibold mb-3">Cues obertes</h3>
          <dl className="grid grid-cols-2 gap-y-1 text-xs">
            <dt className="opacity-60">
              <Link to="/staff/pendents" className="underline hover:text-tq-yellow-deep">Artistes pendents</Link>
            </dt>
            <dd className="text-right font-semibold tabular-nums">{bd.artistes.pendents}</dd>

            <dt className="opacity-60">
              <Link to="/staff/propostes" className="underline hover:text-tq-yellow-deep">Propostes d'artista</Link>
            </dt>
            <dd className="text-right font-semibold tabular-nums">{comunitat.propostes_pendents}</dd>

            <dt className="opacity-60">
              <Link to="/staff/solicituds" className="underline hover:text-tq-yellow-deep">Sol·licituds de gestió</Link>
            </dt>
            <dd className="text-right font-semibold tabular-nums">{comunitat.solicituds_pendents}</dd>

            <dt className="opacity-60">
              <Link to="/staff/feedback" className="underline hover:text-tq-yellow-deep">Feedback obert</Link>
            </dt>
            <dd className="text-right font-semibold tabular-nums">{comunitat.feedback_obert}</dd>
          </dl>
        </div>
      </section>

      {/* ─── Cron health ─── */}
      <section>
        <h2 className="text-sm uppercase tracking-widest text-white/60 mb-2">
          Pipelines (cron)
        </h2>
        <div className="bg-white text-tq-ink rounded-lg p-3">
          <ul>
            {crons.map(c => <CronStatus key={c.name} cron={c} />)}
            {crons.length === 0 && (
              <p className="text-xs text-tq-ink/60 p-3">
                Sense dades de cron disponibles. Comprova que
                <code>/var/log/topquaranta/status/</code> existeix i és llegible.
              </p>
            )}
          </ul>
        </div>
      </section>

      {/* ─── ML ─── */}
      <section>
        <h2 className="text-sm uppercase tracking-widest text-white/60 mb-2">
          Machine Learning
        </h2>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-3">
          <BigNumber
            label="Features totals"
            value={ml.features_total}
            sub={ml.noise_count != null ? `${ml.noise_count} amb <0,05% impacte` : undefined}
          />
          <BigNumber
            label="Training set"
            value={ml.training_size}
            sub={
              ml.class_balance
                ? `${ml.class_balance.aprovades} aprov. · ${ml.class_balance.rebutjades} rebuig`
                : undefined
            }
          />
          <BigNumber
            label="Confiança mitjana"
            value={ml.confianca_avg != null ? ml.confianca_avg.toFixed(3) : '—'}
            sub={
              ml.confianca_min != null
                ? `rang ${ml.confianca_min}–${ml.confianca_max}`
                : undefined
            }
          />
          <BigNumber
            label="Cançons classificades"
            value={clsTotal}
            sub={clsNone ? `${clsNone} encara sense classe` : undefined}
            tone="yellow"
          />
        </div>

        <div className="grid lg:grid-cols-[1fr_1fr] gap-3">
          <div className="bg-white text-tq-ink rounded-lg p-4">
            <h3 className="text-sm font-semibold mb-3">Distribució de classes</h3>
            <StackedBar
              total={clsTotal}
              segments={[
                { label: 'A (aprova)',    value: clsA,    color: '#10b981' },
                { label: 'B (dubte)',     value: clsB,    color: '#facc15' },
                { label: 'C (rebutja)',   value: clsC,    color: '#ef4444' },
                { label: 'Sense classe',  value: clsNone, color: '#d1d5db' },
              ]}
            />
            {ml.model_mtime && (
              <p className="text-[11px] opacity-60 mt-3">
                Model re-entrenat: {ml.model_mtime.slice(0, 16).replace('T', ' ')}
              </p>
            )}
          </div>

          <div className="bg-white text-tq-ink rounded-lg p-4">
            <h3 className="text-sm font-semibold mb-3">
              Importància de features (top 20)
            </h3>
            <HorizontalBars
              items={topImportances}
              max={maxImp}
              formatValue={v => (v * 100).toFixed(2) + '%'}
            />
            {ml.importances.length > 20 && (
              <p className="text-[11px] opacity-60 mt-3">
                {ml.importances.length - 20} features més amb importància residual.
              </p>
            )}
          </div>
        </div>
      </section>
    </section>
  )
}
