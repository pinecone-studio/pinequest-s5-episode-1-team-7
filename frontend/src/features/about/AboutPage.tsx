import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { useModelInfo } from '../../shared/api/queries.ts'
import type { ModelCard } from '../../shared/api/types.ts'
import { useDocumentTitle } from '../../shared/lib/hooks.ts'
import { Alert } from '../../shared/ui/Alert.tsx'

const pct = (share: number) => `${(share * 100).toFixed(1)}%`

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-2">
      <h2 className="text-sm font-semibold">{title}</h2>
      {children}
    </section>
  )
}

function Facts({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
      {rows.map(([term, value]) => (
        <div key={term} className="contents">
          <dt className="text-slate-500">{term}</dt>
          <dd className="min-w-0 break-words">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

function Table({ head, rows }: { head: string[]; rows: ReactNode[][] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="bg-slate-50 dark:bg-slate-800/50">
            {head.map((h) => (
              <th key={h} scope="col" className="px-3 py-2 font-medium text-slate-600 dark:text-slate-300">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
          {rows.map((cells, i) => (
            <tr key={i}>
              {cells.map((c, j) => (
                <td key={j} className="px-3 py-1.5 tabular-nums">
                  {c}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** What AI scores the slides: model card plus live status (GET /model). */
export function AboutPage() {
  const { t } = useTranslation(['about', 'common'])
  const model = useModelInfo()
  useDocumentTitle(`${t('title')} · PathTriage`)

  return (
    <main className="mx-auto max-w-3xl space-y-8 p-4 md:p-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{t('title')}</h1>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{t('intro')}</p>
      </div>

      {model.isPending && <p className="text-sm text-slate-500">{t('common:status.loading')}</p>}
      {model.error && <Alert tone="error">{t('unavailable')}</Alert>}
      {model.data && (model.data.card ? <ModelCardView card={model.data.card} fileName={model.data.file.name} provider={model.data.provider} matches={model.data.file.matches_card} /> : <Alert tone="error">{t('unavailable')}</Alert>)}
    </main>
  )
}

function ModelCardView({ card, fileName, provider, matches }: { card: ModelCard; fileName: string | null; provider: string | null; matches: boolean }) {
  const { t } = useTranslation(['about', 'common'])
  const patch = card.patch_metrics
  const slide = card.slide_metrics
  const tuned = slide.tuned ? new Date(slide.tuned).toLocaleDateString() : null

  return (
    <>
      <Section title={t('identity.title')}>
        <Facts
          rows={[
            [t('identity.name'), card.name],
            [t('identity.version'), <code key="v">{card.version}</code>],
            [t('identity.file'), <code key="f">{card.file.name}</code>],
            [t('identity.sha'), <code key="s" className="break-all text-xs">{card.file.sha256}</code>],
            [t('identity.size'), `${card.file.size_mb} MB`],
            [t('identity.arch'), `${card.architecture.name} (${card.architecture.params.toLocaleString()} parameters)`],
            [t('identity.input'), t('identity.inputValue', { px: card.architecture.input_px, scale: card.architecture.input_scale_um_per_px })],
            [t('identity.dataset'), card.provenance.dataset],
            [t('identity.backbone'), card.provenance.backbone],
            [t('identity.training'), card.provenance.training],
            [t('identity.distilled'), card.provenance.distilled_from],
            [t('identity.dateTrained'), card.provenance.date_trained ? new Date(card.provenance.date_trained).toLocaleDateString() : t('identity.unknownDate')],
          ]}
        />
      </Section>

      <Section title={t('runtime.title')}>
        <p className="text-sm">{t('runtime.offline')}</p>
        <Facts
          rows={[
            [t('runtime.provider'), provider ?? t('runtime.providerUnknown')],
            [t('runtime.perSlide'), `≈${card.runtime.measured_per_slide_s.value} s (${card.runtime.measured_per_slide_s.context})`],
          ]}
        />
        {fileName && !matches && <Alert tone="warning">{t('runtime.mismatch', { name: fileName, version: card.version })}</Alert>}
      </Section>

      <Section title={t('patch.title')}>
        <p className="text-xs text-slate-500">{t('patch.split')}: {patch.split}</p>
        <Table
          head={[t('patch.threshold'), t('patch.auc'), t('patch.accuracy'), t('patch.sensitivity'), t('patch.specificity')]}
          rows={[[patch.threshold, patch.auc.toFixed(4), patch.accuracy.toFixed(4), patch.sensitivity.toFixed(4), patch.specificity.toFixed(4)]]}
        />
        <p className="text-xs text-slate-500">
          {t('patch.op90', { threshold: patch.at_90_sensitivity.threshold, sens: patch.at_90_sensitivity.sensitivity.toFixed(3), spec: patch.at_90_sensitivity.specificity.toFixed(3) })}
        </p>
      </Section>

      <Section title={t('slide.title')}>
        <p className="text-xs text-slate-500">{t('slide.formula', { formula: slide.formula })}</p>
        <p className="text-xs text-slate-500">
          {tuned ? t('slide.thresholds', { red: slide.thresholds.red, yellow: slide.thresholds.yellow, when: tuned }) : t('slide.thresholdsUnknown', { red: slide.thresholds.red, yellow: slide.thresholds.yellow })}
        </p>
        <Table
          head={[t('slide.fraction'), t('slide.auc'), t('slide.red'), t('slide.yellowOrRed')]}
          rows={[
            [t('slide.normal'), '—', pct(slide.normal_slides.red), pct(slide.normal_slides.yellow_or_red)],
            ...Object.entries(slide.tumour_fractions).map(([frac, s]) => [
              frac.replace('tumour_', '').replace('pct', '%'),
              s.auc == null ? '—' : s.auc.toFixed(4),
              pct(s.red),
              pct(s.yellow_or_red),
            ]),
          ]}
        />
      </Section>

      <Section title={t('plism.title')}>
        <p className="text-xs text-slate-500">{t('plism.note', { metric: card.plism.metric, at: card.plism.at })}</p>
        <Table
          head={[t('plism.device'), t('plism.kind'), t('plism.flagged')]}
          rows={[
            ...Object.entries(card.plism.scanners).map(([device, share]) => [device, t('plism.scanner'), pct(share)]),
            ...Object.entries(card.plism.phones).map(([device, share]) => [device, t('plism.phone'), pct(share)]),
          ]}
        />
      </Section>

      <Section title={t('comparison.title')}>
        <Table
          head={[t('comparison.model'), t('comparison.auc'), t('comparison.size'), t('comparison.speed'), t('comparison.note')]}
          rows={card.comparison.map((row) => [
            row.model,
            row.pcam_auc == null ? '—' : row.pcam_auc.toFixed(4),
            row.size_mb == null ? '—' : `${row.size_mb} MB`,
            row.per_slide_s == null ? '—' : `≈${row.per_slide_s} s`,
            <span key="n" className="text-xs text-slate-500">{row.note}</span>,
          ])}
        />
      </Section>

      <Section title={t('limitations.title')}>
        <ul className="list-disc space-y-1 pl-5 text-sm">
          {card.limitations.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </Section>
    </>
  )
}
