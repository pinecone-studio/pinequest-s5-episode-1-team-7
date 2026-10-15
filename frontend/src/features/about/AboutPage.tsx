import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { useModelInfo, useOrgans } from '../../shared/api/queries.ts'
import type { ModelCard } from '../../shared/api/types.ts'
import { useDocumentTitle } from '../../shared/lib/hooks.ts'
import { Alert } from '../../shared/ui/Alert.tsx'
import { fieldClass } from '../../shared/ui/field.ts'

/** AUC to 3 decimals, but never rounded up to a "perfect" 1.000. */
const formatAuc = (auc: number) => (auc >= 0.9995 && auc < 1 ? auc.toFixed(4) : auc.toFixed(3))

/** "NCT-CRC-HE-100K (...), CC BY 4.0, via Hugging Face x/y" -> without the download mirror. */
const datasetName = (dataset: string) => dataset.split(', via ')[0]

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="font-display text-sm font-bold tracking-[-0.01em]">{title}</h2>
      {children}
    </section>
  )
}

function Facts({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
      {rows.map(([term, value]) => (
        <div key={term} className="contents">
          <dt className="text-ink-faint">{term}</dt>
          <dd className="min-w-0 break-words">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

/** What AI scores the slides: one model card per organ (GET /model?organ=). */
export function AboutPage() {
  const { t } = useTranslation(['about', 'common'])
  const organs = useOrgans()
  const organList = Array.isArray(organs.data) ? organs.data : []
  const [organ, setOrgan] = useState<string | null>(null)
  // Default to lymph node (also what old slides used); fall back to the first listed organ.
  const selected = organ ?? (organList.includes('lymph_node') ? 'lymph_node' : organList[0] ?? null)
  const model = useModelInfo(selected)
  useDocumentTitle(`${t('title')} · PathTriage`)

  return (
    <main className="mx-auto max-w-3xl space-y-8 p-4 md:p-6">
      <div>
        <h1 className="font-display text-[22px] font-bold tracking-[-0.02em]">{t('title')}</h1>
        <p className="mt-1 text-sm text-ink-dim">{t('intro')}</p>
      </div>

      {organList.length > 1 && (
        <label className="block max-w-xs">
          <span className="mb-1 block text-xs font-medium text-ink-dim">{t('organ.label')}</span>
          <select className={fieldClass} value={selected ?? ''} onChange={(e) => setOrgan(e.target.value || null)}>
            {organList.map((o) => (
              <option key={o} value={o}>
                {t(`common:organ.names.${o}`, { defaultValue: o })}
              </option>
            ))}
          </select>
        </label>
      )}

      {model.isPending && <p className="text-sm text-ink-faint">{t('common:status.loading')}</p>}
      {model.error && <Alert tone="error">{t('unavailable')}</Alert>}
      {model.data &&
        (model.data.card ? (
          <ModelCardView card={model.data.card} fileName={model.data.file.name} provider={model.data.provider} matches={model.data.file.matches_card} />
        ) : (
          <Alert tone="error">{t('unavailable')}</Alert>
        ))}
    </main>
  )
}

function ModelCardView({ card, fileName, provider, matches }: { card: ModelCard; fileName: string | null; provider: string | null; matches: boolean }) {
  const { t } = useTranslation(['about', 'common'])
  const patch = card.patch_metrics
  const slide = card.slide_metrics
  const yesNo = (v: boolean | null | undefined) => (v == null ? '—' : v ? t('compare.yes') : t('compare.no'))

  return (
    <>
      <Section title={t('model.title')}>
        <Facts
          rows={[
            [t('model.name'), card.name],
            [t('model.dataset'), datasetName(card.provenance.dataset)],
            [
              t('model.runs'),
              <span key="r">
                {t('model.local')}
                {provider && <span className="ml-1 text-xs text-ink-faint">({provider})</span>}
              </span>,
            ],
            [t('model.size'), `${card.file.size_mb} MB`],
            [t('model.speed'), t('model.speedValue', { s: card.runtime.measured_per_slide_s.value })],
            [t('model.accuracy'), t('model.accuracyValue', { auc: formatAuc(patch.auc), split: patch.split })],
          ]}
        />
        {fileName && !matches && <Alert tone="warning">{t('mismatch', { name: fileName, version: card.version })}</Alert>}
      </Section>

      <Section title={t('compare.title')}>
        <div className="overflow-x-auto rounded-lg border border-line-soft">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="bg-raised/40">
                {[t('compare.model'), t('compare.auc'), t('compare.size'), t('compare.speed'), t('compare.clinicPc')].map((h) => (
                  <th key={h} scope="col" className="px-3 py-2 font-medium text-ink-dim">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-line-soft">
              {card.comparison.map((row, i) => {
                const auc = row.test_auc ?? row.pcam_auc
                return (
                  <tr key={row.model} className={i === 0 ? 'bg-mist-wash/40 font-semibold' : undefined}>
                    <td className="px-3 py-2">
                      {row.model}
                      <span className="block text-xs font-normal text-ink-faint">{row.note}</span>
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap tabular-nums">{auc == null ? '—' : formatAuc(auc)}</td>
                    <td className="px-3 py-2 whitespace-nowrap tabular-nums">{row.size_mb == null ? '—' : `${row.size_mb} MB`}</td>
                    <td className="px-3 py-2 whitespace-nowrap tabular-nums">{row.per_slide_s == null ? '—' : `≈${row.per_slide_s} s`}</td>
                    <td className="px-3 py-2">{yesNo(row.clinic_pc)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <p className="text-xs leading-relaxed text-ink-faint">
          {t('compare.aucHelp')}{' '}
          {card.literature.source && (
            <>
              {t('compare.published')}{' '}
              {card.literature.url ? (
                <a href={card.literature.url} target="_blank" rel="noreferrer" className="underline hover:text-ink">
                  {card.literature.source}
                </a>
              ) : (
                card.literature.source
              )}
              .
            </>
          )}
        </p>
      </Section>

      <details className="group rounded-lg border border-line-soft px-4 py-3 text-sm">
        <summary className="cursor-pointer font-display font-bold text-ink-dim group-open:mb-3">{t('details.title')}</summary>
        <div className="space-y-4">
          <Facts
            rows={[
              [t('details.version'), <code key="v">{card.version}</code>],
              [t('details.sha'), <code key="s" className="break-all text-xs">{card.file.sha256}</code>],
              [t('details.input'), t('details.inputValue', { px: card.architecture.input_px, scale: card.architecture.input_scale_um_per_px })],
              [t('details.flags'), t('details.flagsValue', { red: slide.thresholds.red, yellow: slide.thresholds.yellow })],
            ]}
          />
          <div>
            <h3 className="mb-1.5 text-xs font-semibold text-ink-dim">{t('details.limitations')}</h3>
            <ul className="list-disc space-y-1.5 pl-5 leading-relaxed text-ink-dim">
              {card.limitations.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        </div>
      </details>
    </>
  )
}
