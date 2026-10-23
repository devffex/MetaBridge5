# MetaBridge5 Visual Asset Suite

This directory contains the production-grade visual asset suite for **MetaBridge5**, generated according to the [`background-removal`](../../agents/skills/ux-ui/background-removal/SKILL.md) and [`flat-vector`](../../agents/skills/ux-ui/illustrations-mockup/flat-vector/SKILL.md) design system specifications.

All assets are optimized for web browsers, progressive web apps (PWAs), mobile operating systems, social sharing previews, and developer documentation.

---

## 1. Directory Inventory

| Asset Name | Dimensions | Format | Description / Primary Usage |
| :--- | :---: | :---: | :--- |
| **`logo-transparent.png`** | 1024×1024 | PNG | Master high-res transparent cutout (sub-pixel alpha matting via U2Net) |
| **`logo-transparent.webp`** | 1024×1024 | WebP | Next-gen high-efficiency transparent master |
| **`logo-transparent-512.png`** | 512×512 | PNG | High-DPI transparent logo mark |
| **`logo-transparent-256.png`** | 256×256 | PNG | Standard web app header / navigation logo |
| **`logo-transparent-128.png`** | 128×128 | PNG | Medium thumbnail and avatar badge |
| **`logo-transparent-64.png`** | 64×64 | PNG | Compact UI icon |
| **`logo-dark.png`** | 1024×1024 | PNG | Obsidian slate dark canvas card (`#0B0F19`) |
| **`logo-light.png`** | 1024×1024 | PNG | Crisp white light canvas card (`#FFFFFF`) |
| **`logo-monochrome-white.png`**| 1024×1024 | PNG | Pure white silhouette on transparent canvas (Vercel/GitHub dark mode) |
| **`logo-monochrome-black.png`**| 1024×1024 | PNG | Pure dark slate silhouette on transparent canvas (Vercel/GitHub light mode) |
| **`favicon.ico`** | Multi | ICO | Multi-resolution binary container (16×16, 32×32, 48×48) |
| **`favicon.svg`** | Scalable | SVG | Modern vector favicon with responsive `prefers-color-scheme` CSS support |
| **`favicon-16x16.png`** | 16×16 | PNG | Standard browser tab icon |
| **`favicon-32x32.png`** | 32×32 | PNG | High-DPI retina browser tab icon |
| **`favicon-48x48.png`** | 48×48 | PNG | Windows taskbar and desktop shortcut icon |
| **`apple-touch-icon.png`** | 180×180 | PNG | iOS Safari home screen bookmark icon |
| **`android-chrome-192x192.png`**| 192×192 | PNG | Standard PWA launcher icon |
| **`android-chrome-512x512.png`**| 512×512 | PNG | High-res PWA splash screen icon |
| **`mstile-150x150.png`** | 150×150 | PNG | Windows 10/11 Start menu live tile |
| **`og-image.png`** | 1200×630 | PNG | Open Graph / Twitter Card social preview card |
| **`site.webmanifest`** | Text | JSON | Web App Manifest configuration for PWAs |
| **`logo.svg`** | Scalable | SVG | Mathematical vector emblem (transparent background) |
| **`logo-dark.svg`** | Scalable | SVG | Vector emblem on rounded dark card |
| **`logo-light.svg`** | Scalable | SVG | Vector emblem on rounded light card |
| **`logo-monochrome.svg`** | Scalable | SVG | Vector pure white monochrome mark |

---

## 2. Recommended HTML Integration (`<head>`)

To embed these assets into web applications, landing pages, or documentation sites:

```html
<!-- Standard Favicons -->
<link rel="icon" type="image/x-icon" href="/assets/favicon.ico">
<link rel="icon" type="image/png" sizes="32x32" href="/assets/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/assets/favicon-16x16.png">
<link rel="icon" type="image/svg+xml" href="/assets/favicon.svg">

<!-- Apple & PWA Mobile Icons -->
<link rel="apple-touch-icon" sizes="180x180" href="/assets/apple-touch-icon.png">
<link rel="manifest" href="/assets/site.webmanifest">
<meta name="theme-color" content="#0B0F19">

<!-- Open Graph / Social Sharing -->
<meta property="og:type" content="website">
<meta property="og:title" content="MetaBridge5: Autonomous MT5 Container & Market Data Gateway">
<meta property="og:description" content="Containerized MetaTrader 5 inside Wine with thread-safe gRPC bridge, real-time Candle 0 streaming, and automated Parquet multi-CDN backfill.">
<meta property="og:image" content="/assets/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">

<!-- Twitter Card -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="MetaBridge5 — Autonomous MT5 Container & Market Data Gateway">
<meta name="twitter:description" content="Containerized MetaTrader 5 inside Wine with thread-safe gRPC bridge and real-time streaming.">
<meta name="twitter:image" content="/assets/og-image.png">
```
