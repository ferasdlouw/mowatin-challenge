// Copyright (c) 2026 Athar Al-Madinah Team (فريق أثر المدينة). All rights reserved.
// Mowatin (مُوطِّن) — Proprietary. Source-available for evaluation only. See LICENSE.
import { Mail, Sparkles, FolderGit2 } from 'lucide-react'
import Logo from './Logo'
import { useLang } from '../lib/i18n'

export default function Footer() {
  const { t } = useLang()
  return (
    <footer id="contact" className="bg-[#0E2F3B] py-[1.8rem] text-white/80">
      <div className="shell flex flex-col items-center justify-between gap-6 text-[0.9rem] xl:w-[82rem] xl:flex-row">
        <Logo light size="sm" />
        <div className="text-center">
          <p className="text-[1.15rem] font-bold text-white">{t('نُعلِّم الآلة لتخدم الرسالة', 'We teach the machine to serve the message')}</p>
          <p className="mt-[0.3rem] flex items-center justify-center gap-[0.4rem] text-[0.78rem] text-white/60"><Sparkles className="h-[0.9rem] w-[0.9rem] text-brand-300" aria-hidden />{t('أداة مدعومة بالذكاء الاصطناعي؛ مخرجاتها تحتاج مراجعة بشرية مؤهلة قبل النشر.', 'AI-assisted tool. Outputs need qualified human review before publication.')}</p>
        </div>
        <div className="flex flex-wrap items-center justify-center gap-[1rem]">
          <a href="/results" className="hover:text-white">{t('النتائج', 'Results')}</a>
          <a href="/developers" className="hover:text-white">{t('للمطوّرين (API)', 'Developers (API)')}</a>
          <a href="/about" className="hover:text-white">{t('المصادر وحقوق النشر', 'Sources & credits')}</a>
          <a href="https://github.com/ferasdlouw/mowatin-challenge" target="_blank" rel="noopener noreferrer" className="flex items-center gap-[0.35rem] hover:text-white"><FolderGit2 className="h-[1rem] w-[1rem]" aria-hidden />{t('المستودع على GitHub', 'GitHub repository')}</a>
          <a href="mailto:fadedalow@gmail.com" className="flex items-center gap-[0.5rem] rounded-full bg-white/10 px-[1rem] py-[0.5rem] transition-colors hover:bg-white/20"><Mail className="h-[1rem] w-[1rem]" aria-hidden /> {t('تواصل معنا', 'Contact')}</a>
          <span className="text-white/60">{t('© 2026 فريق أثر المدينة', '© 2026 Athar Al-Madinah Team')}</span>
        </div>
      </div>
      {/* Required attribution (Tanzil CC BY 3.0, QuranEnc terms): docs/SOURCES.md Q2, T1 */}
      <p className="shell mt-[1.2rem] border-t border-white/10 pt-[1rem] text-center text-[0.76rem] text-white/55 xl:w-[82rem]">
        {t('نص القرآن الكريم: ', 'Qur’an text: ')}<a href="https://tanzil.net" target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 hover:text-white">{t('مشروع تنزيل (tanzil.net)', 'Tanzil Project (tanzil.net)')}</a>
        {' · '}{t('ترجمات المعاني: ', 'Translations of the meanings: ')}<a href="https://quranenc.com" target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 hover:text-white">QuranEnc.com</a>
        {' · '}<a href="/about" className="underline underline-offset-2 hover:text-white">{t('التفاصيل وإشعارات الحقوق', 'Details and notices')}</a>
      </p>
    </footer>
  )
}
