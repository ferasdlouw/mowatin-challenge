// Copyright (c) 2026 Athar Al-Madinah Team (فريق أثر المدينة). All rights reserved.
// Mowatin (مُوطِّن) — Proprietary. Source-available for evaluation only. See LICENSE.
// Mirrors the API contract in docs/ARCHITECTURE.md §4. Keep both in sync.
import { useEffect, useState } from 'react'
import { Copy, Check, Radio, Plug, ShieldCheck, Gauge, BookOpen } from 'lucide-react'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import { API_URL, MODE } from '../lib/api'

const BASE = API_URL || 'https://<api-host>'

const REQ = `{
  "text": "التوحيد أساس الإسلام، وهو إفراد الله بالعبادة.",
  "target_lang": "en",
  "audience": "general_non_muslim",
  "mode": "localize"
}`

const RES = `{
  "segments": [
    {
      "id": 1,
      "source": "التوحيد أساس الإسلام، وهو إفراد الله بالعبادة.",
      "output": "Tawhid (the Oneness of God) is the foundation of Islam: devoting all worship to God alone.",
      "type": "term_heavy",
      "level": "A",
      "locked_terms": [{ "ar": "التوحيد", "out": "Tawhid", "glossary_id": "tawhid" }],
      "marks": ["Tawhid", "Islam", "worship"],
      "sources": [{ "kind": "glossary", "ref": "المسرد: التوحيد" }],
      "confidence": 0.95,
      "flags": []
    }
  ],
  "summary": { "segments": 1, "flagged": 0, "avg_confidence": 0.95 },
  "review_queue": [],
  "disclosure": "مخرجات مدعومة بالذكاء الاصطناعي، وتحتاج مراجعة بشرية مؤهلة قبل النشر."
}`

const SNIPPETS = {
  curl: `curl -X POST ${BASE}/v1/translate \\
  -H "Content-Type: application/json" \\
  -d '${REQ.replace(/\n\s*/g, ' ')}'`,
  JavaScript: `const res = await fetch("${BASE}/v1/translate", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ text, target_lang: "en", audience: "new_muslim" }),
});
const { segments, review_queue } = await res.json();
// لا تنشر المقاطع الموجودة في review_queue قبل اعتماد المراجع
const publishable = segments.filter((s) => !review_queue.includes(s.id));`,
  Python: `import requests

r = requests.post("${BASE}/v1/translate", json={
    "text": text, "target_lang": "fr", "audience": "general_non_muslim",
})
r.raise_for_status()
data = r.json()
for seg in data["segments"]:
    print(seg["type"], seg["confidence"], seg["output"])`,
}

const FIELDS = [
  ['text', 'string', 'النص العربي، حتى 4000 حرف.'],
  ['target_lang', 'en | fr', 'لغة الهدف.'],
  ['audience', 'general_non_muslim | new_muslim | youth | academic', 'يغيّر الأسلوب والشرح، لا المعنى.'],
  ['mode', 'localize | raw | compare', 'raw: النموذج نفسه بلا مُوطِّن (للمقارنة). compare: الاثنان معًا.'],
]
const OUT = [
  ['type', 'quran | hadith | term_heavy | general | fatwa_like', 'نوع المقطع.'],
  ['level', 'A | B | C | D', 'مستوى المحتوى (أ–د) وفق الحزمة العلمية للتحدي.'],
  ['output', 'string | null', 'null يعني أن المقطع أُوقف وأُحيل للمراجعة.'],
  ['confidence', '0 – 1', 'من طبقة التحقق. أقل من 0.75 يُحال تلقائيًا.'],
  ['verification', 'verified_retrieval | ambiguous_verse | null', 'للآيات: verified_retrieval ترجمة معتمدة مسترجعة من المصدر لموضع واحد (لا تدخل في متوسط الثقة)؛ ambiguous_verse نص في أكثر من موضع، يُحال إلى المراجع الشرعي.'],
  ['candidates[]', '{ ref, ar, en, fr, en_edition, fr_edition }', 'مواضع النص حين يرد في أكثر من موضع، مع ترجمة معانيها المعتمدة.'],
  ['flags[]', '{ severity: info | warn | block, text }', 'تنبيهات بالعربية جاهزة للعرض.'],
  ['sources[]', '{ kind, ref, edition?, grade? }', 'مصدر كل آية أو حديث أو مصطلح.'],
  ['review_queue', 'number[]', 'معرّفات المقاطع التي لا تُنشر قبل اعتماد المراجع.'],
]

function Code({ children, lang }) {
  const [ok, setOk] = useState(false)
  return (
    <div className="relative">
      <button type="button" onClick={async () => { try { await navigator.clipboard.writeText(children); setOk(true); setTimeout(() => setOk(false), 1400) } catch { /* blocked */ } }}
        className="absolute left-[0.6rem] top-[0.6rem] z-10 inline-flex items-center gap-[0.3rem] rounded-[0.5rem] bg-white/10 px-[0.6rem] py-[0.25rem] text-[0.74rem] font-bold text-white hover:bg-white/20" aria-label="نسخ الكود">
        {ok ? <Check className="h-[0.8rem] w-[0.8rem]" /> : <Copy className="h-[0.8rem] w-[0.8rem]" />}{ok ? 'نُسخ' : 'نسخ'}
      </button>
      <pre dir="ltr" aria-label={lang} className="overflow-x-auto rounded-[0.9rem] bg-ink-900 p-[1rem] pt-[2.4rem] text-left font-mono text-[0.8rem] leading-[1.45rem] text-brand-100"><code>{children}</code></pre>
    </div>
  )
}

export default function DevelopersPage() {
  useEffect(() => { document.title = 'للمطوّرين (API) · مُوطِّن' }, [])
  const [tab, setTab] = useState('curl')
  return (
    <>
      <Navbar />
      <main className="bg-[#F6F9F8]">
        <section className="shell pb-[1.5rem] pt-[3rem] xl:w-[82rem]">
          <div className="flex flex-wrap items-center gap-[0.6rem]">
            <span className={`inline-flex items-center gap-[0.35rem] rounded-full px-[0.8rem] py-[0.25rem] text-[0.8rem] font-bold ${MODE === 'live' ? 'bg-brand-50 text-brand-800' : 'bg-pending-bg text-pending-fg'}`}>
              <Radio className="h-[0.85rem] w-[0.85rem]" aria-hidden />{MODE === 'live' ? 'الخادم متصل' : 'الخادم قيد الإطلاق'}
            </span>
            <span className="text-[0.85rem] font-bold text-brand-800">نُعلِّم الآلة لتخدم الرسالة</span>
          </div>
          <h1 className="mt-[1rem] text-[2.1rem] font-extrabold text-ink-900 xl:text-[2.6rem]">مُوطِّن للمطوّرين</h1>
          <p className="mt-[0.7rem] max-w-[46rem] text-[1.05rem] leading-[1.85rem] text-ink-900/75">
            أضِف طبقة حماية المعنى الشرعي إلى منصتك أو تطبيقك بطلب واحد. ترسل النص العربي، فتحصل على الترجمة مقطعًا مقطعًا
            مع المصادر ودرجة الثقة وما يحتاج مراجعة بشرية.
          </p>
          <ul className="mt-[1.4rem] grid gap-[0.8rem] sm:grid-cols-2 xl:grid-cols-4">
            {[[Plug, 'نقطة واحدة', 'POST /v1/translate'], [ShieldCheck, 'لا نشر بلا مراجعة', 'review_queue يحدد ما يُوقف'], [BookOpen, 'كل مقطع بمصدره', 'المسرد والترجمات المعتمدة'], [Gauge, 'درجة ثقة', 'لكل مقطع، من طبقة تحقق مستقلة']].map(([I, t, d]) => (
              <li key={t} className="flex items-start gap-[0.7rem] rounded-[1rem] border border-slate-200/70 bg-white p-[0.9rem]">
                <span className="grid h-[2.4rem] w-[2.4rem] shrink-0 place-items-center rounded-full bg-brand-100 text-brand-800"><I className="h-[1.1rem] w-[1.1rem]" aria-hidden /></span>
                <span><b className="block text-[0.95rem]">{t}</b><span className={`text-[0.8rem] text-ink-600 ${t === 'نقطة واحدة' ? 'latin' : ''}`}>{d}</span></span>
              </li>
            ))}
          </ul>
        </section>

        <section className="shell grid grid-cols-1 gap-[1.4rem] pb-[2rem] xl:w-[82rem] xl:grid-cols-2">
          <div className="min-w-0">
            <h2 className="text-[1.35rem] font-extrabold">الطلب</h2>
            <p className="latin mt-[0.3rem] text-right text-[0.9rem] font-semibold text-brand-800">POST /v1/translate</p>
            <div className="mt-[0.8rem]"><Code lang="json">{REQ}</Code></div>
            <Table rows={FIELDS} />
          </div>
          <div className="min-w-0">
            <h2 className="text-[1.35rem] font-extrabold">الاستجابة</h2>
            <p className="mt-[0.3rem] text-[0.9rem] text-ink-600">مقطعًا مقطعًا، مع المصدر والثقة والتنبيهات.</p>
            <div className="mt-[0.8rem]"><Code lang="json">{RES}</Code></div>
            <Table rows={OUT} />
          </div>
        </section>

        <section className="shell pb-[2rem] xl:w-[82rem]">
          <h2 className="text-[1.35rem] font-extrabold">أمثلة</h2>
          <div className="mt-[0.8rem] inline-flex rounded-[0.7rem] bg-white p-[0.25rem] shadow-sm" dir="ltr">
            {Object.keys(SNIPPETS).map((k) => (
              <button key={k} type="button" onClick={() => setTab(k)} aria-pressed={tab === k}
                className={`latin rounded-[0.5rem] px-[0.9rem] py-[0.35rem] text-[0.84rem] font-semibold ${tab === k ? 'bg-brand-800 text-white' : 'text-ink-600 hover:text-ink-900'}`}>{k}</button>
            ))}
          </div>
          <div className="mt-[0.7rem]"><Code lang={tab}>{SNIPPETS[tab]}</Code></div>
        </section>

        <section className="shell pb-[3rem] xl:w-[82rem]">
          <div className="grid gap-[1rem] xl:grid-cols-2">
            <div className="rounded-[1.1rem] border border-slate-200/70 bg-white p-[1.2rem]">
              <h2 className="text-[1.15rem] font-extrabold">الأخطاء</h2>
              <ul className="mt-[0.6rem] space-y-[0.35rem] text-[0.9rem]">
                {[['400', 'مدخل غير صالح'], ['413', 'النص أطول من 4000 حرف'], ['429', 'تجاوز حد الطلبات'], ['5xx', 'الخادم لا يستجيب؛ أعد المحاولة بعد لحظات']].map(([c, d]) => (
                  <li key={c} className="flex gap-[0.7rem]"><code className="latin w-[2.6rem] font-semibold text-danger-fg">{c}</code><span className="text-ink-900/80">{d}</span></li>
                ))}
              </ul>
            </div>
            <div className="rounded-[1.1rem] border border-slate-200/70 bg-white p-[1.2rem]">
              <h2 className="text-[1.15rem] font-extrabold">قواعد الاستخدام</h2>
              <ul className="mt-[0.6rem] list-disc space-y-[0.35rem] pr-[1.1rem] text-[0.9rem] leading-[1.6rem] text-ink-900/80">
                <li>لا تنشر أي مقطع في <span className="latin">review_queue</span> قبل اعتماده من مراجع مؤهل.</li>
                <li>اعرض نص <span className="latin">disclosure</span> للمستخدم النهائي.</li>
                <li>لا ترسل بيانات شخصية؛ الخدمة لا تحفظ النصوص.</li>
                <li>مفاتيح الوصول للجهات وحدود الطلبات تُعلن عند الإطلاق.</li>
              </ul>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </>
  )
}

function Table({ rows }) {
  return (
    <div className="mt-[0.9rem] overflow-x-auto rounded-[0.9rem] border border-slate-200/70 bg-white">
      <table className="w-full min-w-[30rem] text-right text-[0.84rem]">
        <tbody className="divide-y divide-slate-100">
          {rows.map(([k, t, d]) => (
            <tr key={k}>
              <td className="latin whitespace-nowrap px-[0.8rem] py-[0.55rem] text-left font-semibold text-brand-900">{k}</td>
              <td className="latin px-[0.8rem] py-[0.55rem] text-left text-[0.76rem] text-ink-600">{t}</td>
              <td className="px-[0.8rem] py-[0.55rem] text-ink-900/80">{d}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
