# Third-Party Notices and Content Sources / المصادر والتراخيص الخارجية

Mowatin's own code is covered by `LICENSE`. The materials below are **not** owned
by the Mowatin authors. They remain the property of their owners and are used under
their own terms, with attribution.

## Scientific and religious content sources (per the challenge's Reference Framework)

| Content | Source | Use in Mowatin |
|---|---|---|
| Islamic terminology glossary | Al-Jamhara, Islamic Content Vocabulary — islamic-content.com/dictionary | Locked term equivalents; takes priority over machine translation |
| Da'wah topics and content | Digital Da'wah Repository — dawa.center | Test set and source passages |
| Q&A about Islam | "Bayyinat" — dawa.center/file/7937 | Test set |
| Qur'an text and approved translations | King Fahd Glorious Qur'an Printing Complex / quranpedia.net | Verses are inserted from approved translations, never machine-translated |
| Hadith and grading | dorar.net/hadith, shamela.ws | Source and grading are shown with each hadith |

> Fill in each item's exact edition/version and the date retrieved before submission.

## Software dependencies

Versions and licenses as recorded in the package metadata (`pip` for Python, `frontend/package-lock.json` for npm).

### Backend runtime (`backend/requirements.txt`)

| Package | Version | License | Link |
|---|---|---|---|
| FastAPI | 0.142.2 | MIT | github.com/fastapi/fastapi |
| Starlette | 1.7.0 | BSD-3-Clause | github.com/Kludex/starlette |
| Uvicorn (`[standard]`) | 0.34.2 | BSD-3-Clause | uvicorn.org |
| Pydantic | 2.11.3 | MIT | github.com/pydantic/pydantic |
| pydantic-settings | 2.9.1 | MIT | github.com/pydantic/pydantic-settings |
| HTTPX | 0.28.1 | BSD-3-Clause | github.com/encode/httpx |

### Backend development and CI only (`backend/requirements-dev.txt`, not shipped)

| Package | License | Link |
|---|---|---|
| pytest | MIT | docs.pytest.org |
| pytest-cov | MIT | github.com/pytest-dev/pytest-cov |
| pytest-asyncio | Apache-2.0 | github.com/pytest-dev/pytest-asyncio |
| respx | BSD-3-Clause | lundberg.github.io/respx |
| Ruff | MIT | docs.astral.sh/ruff |
| Bandit | Apache-2.0 | bandit.readthedocs.io |
| pip-audit | Apache-2.0 | pypi.org/project/pip-audit |

### Frontend runtime (`frontend/package.json` dependencies)

| Package | Version (lockfile) | License |
|---|---|---|
| react, react-dom | 19.3.0 | MIT |
| lucide-react | 1.49.0 | ISC |
| mammoth | 1.13.0 | BSD-2-Clause |
| pdfjs-dist | 6.3.289 | Apache-2.0 |
| @fontsource/amiri-quran, @fontsource/inter, @fontsource/tajawal | 5.3.0 | OFL-1.1 (fonts) |

Frontend build tools (`devDependencies`: Vite, Tailwind CSS, PostCSS, Autoprefixer, oxlint, @vitejs/plugin-react, @types/react*) are used at build time only; their licenses are in `frontend/package-lock.json`.

## AI services used

| Service / Model | Purpose |
|---|---|
| Gemini 3.5 Flash-Lite (`gemini-3.5-flash-lite`, Google AI Studio free tier) | Primary localizer (docs/DECISIONS.md D-028) |
| Qwen3.8 27B (`qwen/qwen3.8-27b:free`) via OpenRouter, free variant | Fallback localizer, different company (D-029) |
| Gemini 3.1 Flash-Lite (`gemini-3.1-flash-lite`, Google AI Studio free tier) | Judge in the verifier, a different model from the localizer (D-030) |

Models are chosen through environment variables (`.env.example`); no key is stored in the repository.

Free tiers: the providers' terms may allow them to use submitted text to improve their services ([Gemini API terms](https://ai.google.dev/gemini-api/terms), [OpenRouter terms](https://openrouter.ai/terms), [OpenRouter privacy](https://openrouter.ai/privacy)). See docs/AI_APPROACH.md and D-033.

Outputs are AI-assisted; see the README for the human review process.

## Development tools (not part of the shipped product)

| Tool | License | Source | Purpose |
|---|---|---|---|
| Impeccable (Claude Code design skill), v4.4.0 | Apache-2.0 | github.com/pbakaus/impeccable @ c74755d — copy in `.claude/skills/impeccable/` | UI design review, audit and polish guidance during development |

## Tanzil Quran Text

The Arabic Quran text (`data/quran/tanzil/quran-simple-clean.txt`) is provided by [Tanzil.net](https://tanzil.net). It is used unmodified (simple-clean format) and is licensed under the Creative Commons Attribution 3.0 License (CC BY 3.0). Terms (see [tanzil.net/docs/text_license](https://tanzil.net/docs/text_license) and `docs/SOURCES.md` Q2): verbatim copying and distribution are allowed, **changing the text is not**, and Tanzil must be credited with a link to tanzil.net and its copyright notice included.

Tanzil copyright notice, reproduced verbatim from [tanzil.net/docs/text_license](https://tanzil.net/docs/text_license) (retrieved 2026-10-03). It applies to `data/quran/tanzil/quran-simple-clean.txt`, a verbatim copy of the Tanzil text:

```text
  Tanzil Quran Text 
  Copyright (C) 2007-2021 Tanzil Project
  License: Creative Commons Attribution 3.0 

  This copy of the Quran text is carefully produced, highly 
  verified and continuously monitored by a group of specialists 
  in Tanzil Project.

  TERMS OF USE:
 
  - Permission is granted to copy and distribute verbatim copies 
    of this text, but CHANGING IT IS NOT ALLOWED.

  - This Quran text can be used in any website or application, 
    provided that its source (Tanzil Project) is clearly indicated, 
    and a link is made to tanzil.net to enable users to keep
    track of changes.

  - This copyright notice shall be included in all verbatim copies 
    of the text, and shall be reproduced appropriately in all files 
    derived from or containing substantial portion of this text.

  Please check updates at: http://tanzil.net/updates/
```

## Translations of the meanings of the Qur'an — QuranEnc.com

Mowatin inserts verse translations from these two files; the LLM never translates a verse. Details are taken from each file's metadata and `docs/SOURCES.md` (T1).

| | English | French |
|---|---|---|
| Translation | Saheeh International | Rachid Maach (Rashid Ma'ash) |
| Publisher | Noor International Center, via QuranEnc.com (Encyclopedia of the Noble Qur'an) | QuranEnc.com (Encyclopedia of the Noble Qur'an) |
| QuranEnc ID | `english_saheeh` | `french_rashid` |
| Version | `v1.1.2-csv.1` (last update 2025-06-24) | `v1.0.3-csv.1` (last update 2026-06-21) |
| Source | [quranenc.com/en/browse/english_saheeh](https://quranenc.com/en/browse/english_saheeh) | [quranenc.com/en/browse/french_rashid](https://quranenc.com/en/browse/french_rashid) |
| Retrieved | 2026-10-02 | 2026-10-02 |
| File in this repo | `data/quran/translations/en.json` | `data/quran/translations/fr.json` |
| Original download | `data/quran/translations/source/english_saheeh_v1.1.2-csv.1.csv` | `data/quran/translations/source/french_rashid_v1.0.3-csv.1.csv` |

QuranEnc.com terms («Contents of the translations can be downloaded and re-published, with the following terms and conditions»):

1. No modification, addition, or deletion of the content.
2. Clearly referring to the publisher and the source (QuranEnc.com).
3. Mentioning the version number.
4. Keeping the transcript information in the document.
5. Notifying the source (QuranEnc.com) of any notes on the translation.
6. Updating the translation according to the latest version issued by the source.
7. Avoiding inappropriate advertisements when displaying the translations.

How Mowatin applies them (`docs/SOURCES.md` T1): the verse text is copied verbatim by `scripts/build_quran_translations.py`; only the footnote markers such as `[1]` are taken out of the verse text, and the footnotes are kept in full in the `footnotes` field, so no content is deleted. The original CSV is kept unchanged in `source/`, the version is in the `version` field, the transcript information is in `transcript_info`, and the terms are in `license`. A new QuranEnc release is applied by downloading it to `source/` and re-running the script.
