# Beauty Index release ledger

Production site: https://liambeautyindex.dpdns.org  
Sites project: `appgprj_6ae534c42f588191b0f2a26e03185615`

This ledger records the saved source version and rollback target for every release. Rollback is performed by deploying the selected saved version ID in Sites; it does not rewrite the Google Sheet or the fallback XLSX.

| Version | Change | Source commit | Saved version ID | Deployment ID |
|---|---|---|---|---|
| v1 | Initial Beauty Index dashboard. | `9f249c29bd2fa580e52383e90ef706b1c4af7afc` | `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_9ee2147255088191b2ac4f65dda62ac1` | — |
| v2 | Dedicated public Drive JSON mirror, read-only macro workbook, and five markets. | `49f00169ca24da29b46e70a0209b23251278c149` | `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_ee94bb88211481919d3c0e31b6623228` | `appgdep_6ae53bbefa748191b5314efed4e1e691` |
| v3 | Worker refinements and documentation. | `75fb7a18d89754fdb4abd60b02b125fa86449d38` | `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_961084c18f8c8191a32faf38c2a89079` | — |
| v4 | Fixed inline JavaScript/image error behavior and removed the unwanted “For NohMin” main-page label. | `1542ecdcdad52a0077757983b28275d576f08449` | `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_bba1098eb70881918ab7bdcaa163dd64` | `appgdep_6ae5df2c6bf481918c7bab1749036968` |
| v5 | Incremental browser and image-link UX refinements; detailed rationale was not retained in the current release notes. | `ab1898425135850089d4e2bd1fa01de7b25acd3e` | `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_ea45d4d0a9188191a61111828a7e3cb4` | — |
| v6 | Incremental browser and image-link UX refinements; detailed rationale was not retained in the current release notes. | `44e8b6b4697879e764d15429cc9e33727421dd1f` | `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_8cc6c8b8d0d481918d30385b19844f85` | — |
| v7 | Expanded image-host CSP, delegated click handlers, Amazon product links, history modal, and tab-specific “For NohMin” display. | `69b4a20d7b0136ed299741de2f72c0ca111aadbf` | `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_ad531dcb3ae4819188ec0b4eb8ea1bdc` | `appgdep_6ae5e2bfa2fc8191afe39e91ca8f8ab5` |
| v8 | Fixed the Brands aggregation runtime bug. | `9375071df1953af2b474df097abb673be85f6325` | `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_b335a1c259f48191bcd85884ad10314a` | `appgdep_6ae5e4cfca048191b4ffbcd122142275` |
| v9 | Added brand intelligence: brand images, search/share, average and best rank, rating/momentum, and sorting. | `9a9a5c206b856c73e1b8411a06e95117b359ff37` | `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_6d5e7367284c8191a4a1e4234ff01a78` | `appgdep_6ae5e975c6b48191b80b3c66b2f410e4` |
| v10 | Improved trend and brand sort explanations, chart styling, and rank/momentum rounding. | `75a296d7a685d14b61aef26df3b5166c2a014aa9` | `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_632612bb2390819182be40d0d3a6244b` | `appgdep_6ae5ed9e1d088191bc04e94913e2c38c` |
| v11 | Added direct product profiles and rank-history tabs, plus overview product trajectories and brand footprint. | `9a304db634820d7f929e2c845e47423465d0f8b0` | `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_83b58445fb148191aa7049a902d6aeb3` | `appgdep_6ae5f1ad425081918aee9682761d58af` |
| v12 | Hotfixed invalid inline client JavaScript that prevented app initialization after v11. | `08aca5593890f936998f129a7198e744574d50bf` | `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_c997ad637d9081918267286791e664c0` | `appgdep_6ae5f47c467c81918167ff57e045d7cc` |
| v13 | Reworked Overview around market pulse and KPIs; added shareable Brand Detail profiles with Overview/Products/Trend tabs. | `1334c7bcf6f9cf3aeccff09119b64fa4aec8a909` | `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_73f4afd3d6a48191b78b9870adc50dee` | `appgdep_6ae5f6d568a0819193023109cf25f099` |
| v14 | Date-aware market pulse, Brands subtabs, archive-wide product search, and chart hover details. | `66a2a459e50a1d7e24ed5f703da378f8ea318be0` | `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_79792b3c682c8191b6b9bfe58a679dd0` | `appgdep_6ae5f9525b808191837eb4b160489a97` |
| v15 | Expanded finder filtering/sorting/pagination and joined product metadata images with an ASIN image fallback. | `361e20943ef002def8c291b91025c7baf94b20fd` | `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_59e1a92b83348191af745cf3628692cb` | `appgdep_6ae5fe25d2b481919fa65106dfd0ec45` |
| v16 | Joined selected-date snapshot images and brands into archive products by ASIN; verified real medicube and CeraVe images. | `0365675578ddc28e73b5c8796324ffdc129808b2` | `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_7ec3d937aa6081918661991aefd9e290` | `appgdep_6ae5ffc6d6248191b69dc4e75c19375b` |
| v17 | Product Finder now starts with a clean search field and no automatic #1 result or oversized tinted count panel; filters are collapsed until requested; product image rendering retries captured candidates and quietly suppresses the “NO PHOTO” label. | `4df35ca023e3d5244288c5c13bfc51c57e28be1e` | `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_0823e4b74810819188c2477d4ee73881` | `appgdep_6ae66342de2c8191a000fe7a89bcee30` (succeeded; `https://liambeautyindex.dpdns.org`) |
| v18 | Product Finder merges the selected market snapshot into archive results, so rank and Last captured reflect Nov 1 KST even though append-only history uses each marketplace's local calendar. | `dc4fb72c38fd180e92c42330a9cf637ca3441def` | `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_fa0d7c1803dc8191ae7076ba454867ff` | `appgdep_6ae6660ed28481918eb19b88614f08c3` (succeeded; `https://liambeautyindex.dpdns.org`) |
| v19 | Unified date context and preserve-date market switching; exact hover/focus/tap chart tooltips and coverage semantics; cross-market movers on Overview; archive Product Finder cache plus first/last-seen/current-rank labels. | `aa2a9e3f2151ea611daa113cb723d873be9bf799` | `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_ea09fb9fee70819184683c638ff5dabd` | `appgdep_6ae6687075fc81918de5021006d94a65` (succeeded; `https://liambeautyindex.dpdns.org`) |
| v20 | v19 hotfix: restore canonical-header layout by nesting date context in the selectors; prevent cached HTML from showing stale releases; hide chart dots until hover/focus and size hit areas for dense sparklines. | `3cb75994e3de4faed5b20b82f52b5afa84f83ca9` | `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_85fa538ac5888191b996cdf26ec74d5d` | `appgdep_6ae66abf161c8191a523d91ed2839cce` (succeeded; `https://liambeautyindex.dpdns.org`) |

Latest rollback target for v20 (v19 hotfix): v19 `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_ea09fb9fee70819184683c638ff5dabd`.

## Future release entry template

Record each release immediately after save/deploy:

```text
### vNN — YYYY-MM-DD
- User-visible change:
- Data/runtime dependencies changed:
- Verification performed and result:
- Source commit:
- Saved Sites version ID:
- Production deployment ID and URL:
- Previous known-good rollback version ID:
```

Keep the prior production version saved. A release is complete only after its deployment reaches `succeeded` and the public page has been checked.
