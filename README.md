# IlmiScrape

Web app sederhana untuk mendownload audio dari YouTube dan video (tanpa watermark) / audio dari TikTok.

## Fitur (MVP)
- Auto-detect URL YouTube dan TikTok.
- Pencarian judul lagu YouTube secara realtime dengan auto-dropdown dan thumbnail.
- Streaming langsung dari server CDN (tidak memakan disk space di server).
- Dukungan konversi MP3 320kbps secara on-the-fly untuk YouTube menggunakan `ffmpeg` tanpa limit limitasi speed.
- UI ringan, 1 halaman, mobile-first dengan Tailwind CSS.
- Caching data info menggunakan memori lokal.

## Cara Menjalankan

Aplikasi ini menggunakan sistem Bypass Anti-Bot YouTube dengan Node.JS dan local proxy HTTP. Aplikasi dijalankan secara native menggunakan `pm2` agar dapat berjalan otomatis di background dan *auto-restart* jika *server reboot*.

```bash
cd /root/clipgrab
pm2 start start.sh --name "ilmiscrape"
pm2 save
```

Aplikasi akan berjalan di port `9002` dan dapat diakses di `http://<IP-SERVER>:9002`.

## Struktur File
- `main.py`: Backend FastAPI (Endpoint UI, Search, dan API Streaming).
- `extractor.py`: Logika ekstraksi URL & Pencarian menggunakan `yt-dlp`.
- `static/index.html`: Frontend UI.
- `requirements.txt`: Dependensi Python.
