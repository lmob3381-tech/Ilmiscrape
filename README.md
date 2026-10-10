<div align="center">
  <img src="https://img.shields.io/badge/Status-Active-success.svg?style=for-the-badge" alt="Status">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python" alt="Python Version">
  <img src="https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/TailwindCSS-38B2AC?style=for-the-badge&logo=tailwind-css" alt="Tailwind">
</div>

<h1 align="center">IlmiScrape 🚀</h1>

<p align="center">
  <b>Advanced Media Downloader & Streamer (Bypass Anti-Bot)</b><br>
  Web app all-in-one minimalis berkinerja tinggi untuk mengunduh, mencari, dan melakukan <i>streaming</i> media secara <i>on-the-fly</i> dari berbagai platform!
</p>

---

## ✨ Fitur Utama

- 🌐 **Multi-Platform Support**: YouTube dan TikTok (tanpa watermark).
- ⚡ **Instant Stream (On-the-fly)**: Konversi format (seperti MP3 320kbps) dikerjakan <i>streaming langsung</i> dari memori / pipa, sehingga tidak membebani <i>disk space</i> server.
- 🔍 **Realtime Auto-Search**: Ketik judul apa saja dan hasil pencarian otomatis muncul dengan *thumbnail* instan.
- 🚀 **Anti-Bot Bypass Engine**: Terintegrasi `curl_cffi` + `yt-dlp` + *Local Proxy Tunneling* (WARP-ready) untuk membypass pemblokiran IP.
- 🎨 **Neo-Brutalist UI**: Desain antarmuka *mobile-first* satu halaman (SPA) elegan dengan sentuhan hitam pekat *OLED-Dark Mode*, bebas animasi yang tidak perlu.
- 🧠 **Smart Caching**: Respon 10x lebih cepat dengan memori Redis (*fallback* ke memori lokal jika tidak tersedia).

---

## 🛠 Instalasi & Menjalankan (Production Mode)

Kami merekomendasikan menggunakan `pm2` untuk menjaga layanan tetap hidup (*auto-restart* & *background process*).

### 1. Persiapan Dependensi

```bash
# Clone repositori Ilmiscrape
git clone https://github.com/lmob3381-tech/Ilmiscrape.git
cd Ilmiscrape

# Buat Virtual Environment (opsional namun direkomendasikan)
python3 -m venv venv
source venv/bin/activate

# Install dependensi utama
pip install -r requirements.txt
pip install curl-cffi  # Untuk impersonate browser & Cloudflare Bypass
```

### 2. Mulai Server

```bash
# Menggunakan PM2 untuk environment produksi
pm2 start start.sh --name "ilmiscrape"
pm2 save
```

Aplikasi sekarang *live* di **http://127.0.0.1:9002** 🚀

---

## 📖 Panduan Penggunaan Pintar (Smart Query)

Anda dapat memaksimalkan fitur *Search Bar* di tampilan antarmuka dengan *prefix* khusus ini:

| Format Query | Contoh | Fungsi |
| :--- | :--- | :--- |
| `[Teks Biasa]` | `lagu terbaru` | Melakukan **pencarian di YouTube**. Otomatis menampilkan opsi MP3/MP4 dan fitur pemutar Audio. |
| `[Link Langsung]` | `https://tiktok.com/...` | Otomatis melewati *search* dan akan **mengekstraksi info URL tersebut secara langsung**. |

---

## 🏗 Struktur Proyek

- 📝 `main.py` - Core Backend FastAPI. Termasuk *router* UI, *proxy endpoint*, dan manajemen *On-The-Fly Streaming*.
- 🕸️ `extractor.py` - "Otak" sistem. Mengelola `yt-dlp`, `curl_cffi`, dan *Regex Scraping* kustom untuk menghindari limitasi *rate/bot-protection*.
- 🎨 `static/index.html` - Frontend modern, ringan (0-bundle), ditenagai CDN Tailwind dan HLS.js.

---

<div align="center">
  <p><b>&copy; 2026 IlmiDev.</b> All rights reserved.</p>
</div>
