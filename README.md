# defproc-monitor

> **Disclaimer:** Independent, non-commercial, informational project — **not affiliated
> with, endorsed by, or connected to** MoD, the Government of India, NIC, GePNIC, or
> defproc.gov.in. All data is aggregated from **publicly accessible** pages of
> defproc.gov.in and reproduced **"as is"**; it may be inaccurate, incomplete, outdated,
> or auto-misclassified, and is **not an official record** — verify against defproc.gov.in.
> Provided with **no warranty and no liability** to the maximum extent permitted by law.
> See [`DISCLAIMER.md`](DISCLAIMER.md). Licensed under **Apache-2.0** (see [`LICENSE`](LICENSE)).

A **free, single-source tender monitor** for [`defproc.gov.in`](https://defproc.gov.in)
(NIC GePNIC, MoD eProcurement). It scrapes public tender listings, tags + geocodes
them, and serves a static public dashboard with two views:

- **Live Monitor** — stream of tenders **published in the last 72 h** + the official
  sovereign map of India + buyer-address flash card, CRITICAL items highlighted.
- **LPP Finder** — searches the active defproc catalogue for the **item + buyer + tender
  reference**, mapped to **DPM 2025** forms (DPMF 5 Ser 7 / Ser 6(a) / DPMF 7) with §5.33.4
  vintage caveats. Awarded prices are captcha-gated on defproc, so this is a reference +
  drafting-skeleton tool, not a price database (the LPP is obtained from the buying unit).

