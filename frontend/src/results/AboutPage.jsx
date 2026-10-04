// Copyright (c) 2026 Athar Al-Madinah Team (فريق أثر المدينة). All rights reserved.
// Mowatin (مُوطِّن) — Proprietary. Source-available for evaluation only. See LICENSE.
//
// Sources and copyright notices required by the Quran text and translation licences
// (docs/SOURCES.md Q2 and T1, THIRD_PARTY_NOTICES.md).
import { useEffect } from 'react'
import { BookOpen, Languages, Library, ExternalLink } from 'lucide-react'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'

// Verbatim from THIRD_PARTY_NOTICES.md (retrieved from tanzil.net/docs/text_license, 2026-10-03). Do not edit.
const TANZIL_NOTICE = "  Tanzil Quran Text \n  Copyright (C) 2007-2021 Tanzil Project\n  License: Creative Commons Attribution 3.0 \n\n  This copy of the Quran text is carefully produced, highly \n  verified and continuously monitored by a group of specialists \n  in Tanzil Project.\n\n  TERMS OF USE:\n \n  - Permission is granted to copy and distribute verbatim copies \n    of this text, but CHANGING IT IS NOT ALLOWED.\n\n  - This Quran text can be used in any website or application, \n    provided that its source (Tanzil Project) is clearly indicated, \n    and a link is made to tanzil.net to enable users to keep\n    track of changes.\n\n  - This copyright notice shall be included in all verbatim copies \n    of the text, and shall be reproduced appropriately in all files \n    derived from or containing substantial portion of this text.\n\n  Please check updates at: http://tanzil.net/updates/\n"

const QURANENC = [
  { lang: 'الإنجليزية', edition: 'Saheeh International', by: 'Saheeh International — Noor International Center', version: 'v1.1.2-csv.1', url: 'https://quranenc.com/en/browse/english_saheeh' },
  { lang: 'الفرنسية', edition: 'Rachid Maach', by: "Rachid Maach (Rashid Ma'ash)", version: 'v1.0.3-csv.1', url: 'https://quranenc.com/en/browse/french_rashid' },
]

const Ext = ({ href, children }) => (
  <a href={href} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-[0.25rem] font-bold text-brand-800 underline-offset-4 hover:underline">
    {children}<ExternalLink className="h-[0.85rem] w-[0.85rem]" aria-hidden />
  </a>
)

function Card({ Icon, title, children }) {
  return (
    <section className="rounded-[1.2rem] border border-slate-200/70 bg-white p-[1.3rem]">
      <h2 className="flex items-center gap-[0.6rem] text-[1.25rem] font-extrabold text-ink-900">
        <span className="grid h-[2.4rem] w-[2.4rem] place-items-center rounded-full bg-brand-100 text-brand-800"><Icon className="h-[1.15rem] w-[1.15rem]" aria-hidden /></span>{title}
      </h2>
      <div className="mt-[0.9rem] space-y-[0.7rem] text-[0.95rem] leading-[1.75rem] text-ink-900/80">{children}</div>
    </section>
  )
}

export default function AboutPage() {
  useEffect(() => { document.title = 'المصادر وحقوق النشر · مُوطِّن' }, [])
  return (
    <>
      <Navbar />
      <main className="bg-[#F6F9F8]">
        <section className="shell space-y-[1rem] pb-[3rem] pt-[3rem] xl:w-[60rem]">
          <h1 className="text-[2rem] font-extrabold text-ink-900">المصادر وحقوق النشر</h1>
          <p className="text-[1rem] leading-[1.8rem] text-ink-900/75">
            لا يترجم مُوطِّن أي آية آليًا: نص الآيات من مشروع تنزيل، وترجمات معانيها تُدرج حرفيًا من ترجمات منشورة على QuranEnc.com مع ذكر مصدرها.
          </p>

          <Card Icon={BookOpen} title="نص القرآن الكريم: مشروع تنزيل">
            <p>
              يُستخدم نص القرآن الكريم من <Ext href="https://tanzil.net">مشروع تنزيل (Tanzil Project)</Ext> كما هو دون أي تعديل،
              بترخيص المشاع الإبداعي (CC BY 3.0). وتُنشر التحديثات على <Ext href="http://tanzil.net/updates/">tanzil.net/updates</Ext>.
            </p>
            <p className="text-[0.85rem] text-ink-600">إشعار الحقوق كما ورد من المصدر:</p>
            <pre dir="ltr" lang="en" className="overflow-x-auto whitespace-pre rounded-[0.8rem] bg-paper p-[0.9rem] text-left font-mono text-[0.78rem] leading-[1.35rem] text-ink-900">{TANZIL_NOTICE}</pre>
          </Card>

          <Card Icon={Languages} title="ترجمات معاني القرآن: QuranEnc.com">
            <p>
              تُدرج ترجمات المعاني حرفيًا، دون تعديل أو إضافة أو حذف، من <Ext href="https://quranenc.com">الموسوعة القرآنية QuranEnc.com</Ext>:
            </p>
            <ul className="space-y-[0.5rem]">
              {QURANENC.map((q) => (
                <li key={q.edition} className="rounded-[0.8rem] bg-paper px-[0.9rem] py-[0.6rem]">
                  <b className="text-ink-900">{q.lang}:</b> <span className="latin">{q.by}</span>
                  <span className="block text-[0.85rem] text-ink-600">الإصدار <span className="latin">{q.version}</span> · <Ext href={q.url}>صفحة الترجمة</Ext></span>
                </li>
              ))}
            </ul>
          </Card>

          <Card Icon={Library} title="المسرد وبقية المصادر">
            <p>
              مصادر المسرد والأحاديث وعبارات الإحالة، وطريقة استخدامها والتحقق منها، موثّقة في ملف
              {' '}<Ext href="https://github.com/ferasdlouw/mowatin-challenge/blob/main/docs/SOURCES.md">docs/SOURCES.md</Ext>،
              وإشعارات المكتبات والخدمات في <Ext href="https://github.com/ferasdlouw/mowatin-challenge/blob/main/THIRD_PARTY_NOTICES.md">THIRD_PARTY_NOTICES.md</Ext>.
            </p>
          </Card>
        </section>
      </main>
      <Footer />
    </>
  )
}
