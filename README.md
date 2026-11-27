# Air Wudhu — Doodle Dakwah Engine

Video animasi doodle (gaya gambar tangan) yang menjelaskan hukum/amalan Islam untuk FB Reels 1080×1920.
Contoh topik: *"Kenapa habis berhubungan suami istri harus mandi wajib?"*

## Menjalankan
Dobel-klik `run_ui.bat` → http://127.0.0.1:8600

## Alur (tab Studio)
1. **Topik**: ketik pertanyaan + sudut cerita (opsional).
2. **Bahan**: engine mencari artikel (Bing/Google via `ddgs`, prioritas situs kajian di Pengaturan) lalu membaca isinya.
   Centang bahan yang dipakai, tambah URL sendiri, atau tempel catatan dari kitab/ustadz.
3. **Naskah**: LLM lokal (Ollama) menyusun 6–8 adegan. Dalil diverifikasi otomatis:
   - Ayat → teks Arab + terjemah **Kemenag** diambil dari API equran.id (bukan dari AI), dan dicek apakah ayat itu
     disebut di bahan.
   - Hadits → kutipan harus ditemukan di teks bahan; kalau tidak → ditandai ⚠️ dan harus dicek manual / dihapus.
4. **Setujui** naskah (wajib — dalil ⚠️ harus dicentang "sudah saya cek" atau dihapus).
5. **Render** → `output/<tanggal>/auto_video_N_final.mp4` + `_caption.txt` (berisi dalil & link rujukan) + `_meta.json`.
6. Tab **Hasil & Upload** → jadwalkan ke Fanspage (Graph API, akun bisa diambil dari engine lain).

## Jenis adegan
`tanya` (hook) · `bicara` (balon + ikon) · `quran` (kartu ayat) · `hadits` (kartu hadits) · `poin` (hikmah + ikon) ·
`langkah` (checklist) · `fakta` (kata besar) · `penutup` (polling A/B di komentar)

## File
| File | Isi |
|---|---|
| `aw_main.py` | CLI: `new`, `research`, `script`, `render`, `auto` |
| `aw_research.py` | pencarian web, pembaca artikel, deteksi & ambil ayat (equran.id, cache di `cache/quran`) |
| `aw_script.py` | prompt storyboard, normalisasi, verifikasi dalil, caption |
| `aw_doodle.py` | primitif doodle (goresan bergetar, draw-on, teks + Arab), ikon, rig tokoh berpeci |
| `aw_render.py` | timeline, TTS (edge-tts), SFX, subtitle, transisi, encode ffmpeg, preview |
| `aw_ai.py` | Ollama (dengan fallback model kecil bila RAM kurang) + edge-tts |
| `aw_upload_fb.py` | jadwal Reels ke Fanspage (pakai `facebook_uploader` dari `criminal_reel_youtube`) |
| `config.json` | pengaturan + gaya tampilan (`style`) |
| `projects/<id>/project.json` | topik, bahan, naskah, status persetujuan, daftar video |

Font: Kalam (tulisan tangan) & Amiri (Arab) — lisensi SIL OFL, di `assets/fonts`. SFX di `assets/sfx`.
Musik latar opsional: taruh mp3 di `assets/bgm` lalu aktifkan di tab Tampilan.

## Catatan
- Laptop ini RAM 8 GB: `gemma2:9b` sering tidak muat → otomatis pindah ke `qwen2.5:3b` (atur di Pengaturan).
- Suara narasi (edge-tts) butuh internet.
- Konten tetap perlu dicek manusia sebelum tayang — engine hanya membantu memastikan dalil berasal dari sumber.

## Efek visual & durasi ±1 menit (aw_fx.py)
Tab **Tampilan** → *Efek visual*: Mati / Halus / Sedang (default) / Maksimal.
- Latar: gelembung, bintang, tetes air melayang pelan.
- Kamera: push-in pelan, denyut zoom di tiap beat (SFX pop/stempel/centang), goyang napas, shake saat stempel dalil.
- Ledakan konfeti/bintang/tetes saat kartu dalil, fakta, poin, centang langkah, penutup; sinar berputar di kata besar.
- Tokoh bernapas & mengangguk saat bicara; ikon melayang.
- Transisi **Variasi** (geser, riak air, tinta, pudar + kilatan putih) atau pilih satu.
- Subtitle menyorot kata yang sedang diucapkan; bar progres emas di atas.
- Durasi: `target_sec` (60) di config.json; engine menyetel kecepatan suara (-10%..+18%) agar hasil ±56–66 dtk.
  Naskah baru: 8–10 adegan, ±`target_words` (140) kata. Naskah lama yang pendek tidak dipanjangkan — buat ulang naskahnya.

## Figur ustad dari foto (aw_figur.py)
Foto `assets/figur-ustad.jpeg` dipotong dari latar, dikartunkan, diberi garis stiker, lalu digerakkan tiap frame:
napas, kepala goyang/mengangguk, kedip, mulut membuka mengikuti suara narasi, ikon ekspresi (!, ?, ★).
Gaya: tab Tampilan → *Figur ustad* (Kartun / Doodle tegas / Foto asli / Tokoh gambar bawaan).
Ganti foto = timpa file itu (foto setengah badan, wajah menghadap depan). Titik mata/mulut ada di `LM` di aw_figur.py
(atau `figur_lm` di config.json) — sesuaikan bila wajah di foto baru posisinya beda. Render ±3× realtime.

## Update: figur ilustrasi + latar meriah (aw_figur.py, aw_bg.py)
- Figur = `assets/figur-ustad.jpeg` (ilustrasi, latar polos dipotong otomatis). Gaya: Asli (default) / Kartun / Doodle / Tokoh bawaan.
  Titik mata & mulut ada di `LM` (aw_figur.py) atau `figur_lm` di config.json bila gambar diganti.
- Latar tiap adegan: awan melayang, bulan sabit, bokeh, siluet masjid + kurma, sinar (dalil/hook/fakta), pola bintang islami (adegan ayat/hadits).
- Halo emas berdenyut + bintang mengorbit di belakang ustad; hujan hati/bintang/konfeti di penutup, fakta, dalil.
- Transisi baru "tirai". Semua ikut tombol Efek visual (Mati/Halus/Sedang/Maksimal).
- Render ±5× durasi video (video 57 dtk ≈ 5 menit).

## Ilustrasi cerita & ucapan Allah (aw_cerita.py, aw_ai.py)
- **Panggung gambar**: saat narasi menyebut *suami, istri, anak, bayi, ibu, ayah, kakek, nenek, teman, keluarga, orang tua* tokoh itu DIGAMBAR (doodle, draw-on) di panggung
  (rumah / luar ruangan) tepat saat kata diucapkan; ustad mengecil ke pojok kanan. Maks. 3 tokoh sekaligus, yang lama keluar bila ada tokoh baru.
- **Ekspresi** mengikuti kata emosi: marah (tanda kemarahan), sedih (air mata), senang/bahagia (tangan naik), cinta/sayang (hujan hati), kaget, bingung.
- **Benda penjelas** (stiker di atas tokoh): rumah, uang/nafkah, kerja, masak, sekolah, masjid, cincin nikah, dll. Tanpa gambar Nabi/sahabat.
- Hanya adegan `tanya` & `bicara`; adegan lain memakai stiker wajah tokoh. Matikan: tab Tampilan -> *Ilustrasi tokoh cerita*.
- **Allah**: tulisan (layar, subtitle, caption) tetap "Allah"; hanya suara yang diucapkan "Awloh" (ejaan fonetik ke TTS, diatur `allah_ucap` di config.json,
  mis. "Alloh"). Majemuk: Subhanallah/Rasulullah/Alhamdulillah -> akhiran "...lloh".
- Naskah baru: prompt meminta kata peran yang jelas bila bahan memuat contoh. Video lama perlu dirender ulang untuk memakai fitur ini.

## Bibir & tangan (aw_figur.py)
- Bibir: rongga mulut mengikuti garis senyum (`seam` di LM), rahang turun dari garis bibir, ada gigi & lidah. Bentuk mulut mengikuti suara:
  frekuensi rendah ("o/u") = bulat & lebih tinggi, tinggi ("e/i") = lebar & tipis.
- Tangan kanan di dada dipisah jadi lapisan sendiri (`hand_poly`, `hand_pivot` di LM) dan digerakkan: menjelaskan (naik-turun + putar, lebih besar saat bicara),
  `tunjuk`, `mikir` (naik ke dagu), `lambai`. Gerak ikut tombol Efek visual (Mati = tangan diam).

## Gambar & efek per kata (aw_kata.py)
Waktu tiap kata diambil dari edge-tts (WordBoundary), jadi gambar muncul TEPAT saat kata diucapkan.
- Kamus `LEX` (≈120 kata + imbuhan: "membasuh"→basuh): ikon, prioritas, efek. Contoh: wudhu/air/basuh → tetes + percikan air; wajah, kepala, telinga, kaki, kumur → ikon anggota wudhu;
  hati/niat/ikhlas → hati + hujan hati; Allah → sinar emas berdenyut; pahala/hikmah/syukur → konfeti; dosa/kotor → awan; surga → pohon; angka (tiga, 3) → lencana angka.
- Stempel besar hanya untuk kata yang diucapkan: WAJIB, SUNNAH, SAH, JANGAN, BATAL (hentakan + kamera bergetar).
- Maks 4 stiker/adegan, jarak ≥1,25 dtk, ikon sama baru muncul lagi setelah 7 dtk. Posisi menghindari tokoh, teks, dan ikon adegan.
- Subtitle memakai waktu kata asli (menyala tepat per kata); kata bermakna menyala merah & lebih besar.
- 12 ikon baru: wajah, kepala, telinga, kaki, mulut, hidung, api, awan, pohon, timbangan, senyum, sedih.
- Matikan/ganti di tab Tampilan → "Gambar per kata". Tambah kata sendiri di `LEX`.

## Dunia sinematik (aw_dunia.py) — latar profesional + simulasi kehidupan
Tab Tampilan -> "Dunia sinematik" (style `dunia`, ikut tombol Efek visual). Backup `*.bak_dunia`.
- **Latar semua adegan**: gradasi langit per jenis adegan (hook biru, dalil emas, fakta jingga, penutup merah muda), bukit parallax 3 lapis berpohon,
  debu cahaya melayang, berkas cahaya, vignette hangat, grain film tipis.
- **Panggung cerita hidup**: ruang tamu lengkap (jendela+tirai, jam dinding yang berjalan, lampu gantung & lampu berdiri, rak buku, bingkai masjid, sinar matahari
  berdebu) atau halaman desa (matahari berputar, awan, kawanan burung, masjid & rumah di kejauhan, jalan dengan mobil lewat, figuran berjalan di trotoar, pohon, bunga).
  Siang/malam (kata *malam, tahajud, subuh*), hujan (kata *hujan*), ramai (kata *jamaah, masyarakat, tetangga, banyak*) = figuran jadi 7 orang.
- **Hewan & benda muncul saat disebut**: kucing, burung, kupu-kupu, bola (anak menendang & memantul), layangan (anak memegang benang). Tanpa kata itu,
  satu penghias bawaan dipilih otomatis (kucing/burung di dalam; kupu-kupu/bola/layangan di luar). Tambah kata di `PROPS` (aw_cerita.py).
- **Efek emosi layar penuh (MoodA)**: marah = awan badai + petir + tepi merah; sedih = hujan + redup biru; senang = pelangi + tepi emas;
  cinta = hati melayang + tepi merah muda; kaget = kilatan putih + garis kecepatan. Panggung membuka dengan gelombang kejut emas.
- Biaya render naik ±0,06 dtk/frame. Matikan lewat toggle atau `style.dunia=false`.

## Hologram tiap kata Gus Idrus (aw_holo.py)
Setiap kata yang diucapkan Gus Idrus muncul sebagai **proyeksi hologram** tepat saat diucapkan (waktu per kata dari edge-tts).
- **Proyektor** di kaki ustad: piringan berputar (lingkar / heksagon bergantian per adegan), lantai grid, denyut cincin tiap kata,
  sorot cahaya yang makin terang saat suara keras, partikel data naik. Saat adegan mulai: efek "boot".
- **Panel kata**: kaca gelap bercahaya, 9 gaya masuk (pindai, glitch, putar 3D, zoom, ketik, naik, piksel, gema, ayun) ×
  5 gaya keluar (naik, pecah, runtuh jadi garis, geser, glitch) — diacak tanpa mengulang gaya berurutan. Kata kecil (yang, di, dan…)
  tampil lebih kecil, kata bermakna lebih besar.
- **Kata penting** → ikon hologram berputar 3D di kaca bulat (menggantikan stiker); kata hukum (WAJIB, JANGAN…) → stempel hologram
  dengan glitch & gelombang kejut. SFX sintetis `holo_boot/holo_on/holo_glitch` (dibuat oleh `_batch/buat_sfx_holo.py`).
- **Warna**: tema bergilir per adegan (sian, toska, ungu, biru), emas untuk ayat/hadits & kata Allah/ibadah, hijau wajib/sunnah/sah,
  merah jangan/haram/batal. HUD sudut panggung + garis pindai.
- **Negasi aman**: "tidak membatalkan" ditampilkan utuh sebagai satu panel warna netral; stempel/ikon/sorotan merah subtitle
  dilewati untuk kata yang disangkal (tidak, bukan, belum, tanpa) supaya hukum tidak terbaca terbalik.
- Atur di tab Tampilan → *Hologram tiap kata*: Semua kata (default) / Kata penting / Mati (`style.holo`).
- Biaya render hologram ±15 ms/frame. Backup sebelum fitur ini: `*.bak_holo`.

## Tata letak "pojok" + cerita stickman (aw_layout.py, aw_stik.py) — default sejak 2026-11-18
- **Tata letak** (tab Tampilan → *Tata letak*): **Cerita besar · ustad pojok** (default) = panggung cerita di atas, kata hologram +
  subtitle **di tengah layar**, Gus Idrus kecil di **pojok kanan bawah** (tidak ada teks menimpa ustad). *Ustad tengah (lama)* tetap ada.
- **Cerita stickman** (adegan `tanya` & `bicara`): saat Gus Idrus menjelaskan, alur cerita diperagakan stickman dalam 1–4 babak
  yang muncul tepat pada kata pemicunya; nomor alur **1 → 2 → 3** muncul di pojok panggung.
  - 45 aksi berpose prosedural (jalan, wudhu, takbir, rukuk, sujud, doa, makan, baca quran, gendong bayi, ngupil, bersin, kerja, masak…),
    10 latar (rumah, kamar, dapur, tempat wudhu, masjid, halaman, jalan, kantor, sekolah, pasar; siang/malam), benda & perabot otomatis
    (sajadah, kran, kasur, kursi, meja-laptop, kompor), efek emosi (air mata, marah, keringat, Zzz, cahaya, tanya, seru).
  - Variasi: tokoh masuk berjalan / muncul / jatuh; transisi babak iris / geser / kilat / tirai; kamera mendorong pelan ke tokoh.
  - **Tiap video beda**: tokoh (jenis & warna baju/hijab), latar dasar, reaksi lawan main, posisi diacak dari judul video.
  - Penyusun cerita default = **otomatis dari kata yang diucapkan** (cepat, selalu nyambung): kata aksi → peragaan, "tapi/namun" → babak
    kontras, "jadi/intinya" → babak paham, boleh/sah/"tidak batal" → senang, batal/jangan → menolak, kalimat tanya → bingung.
    Opsional `"stik_llm": true` di config.json → disusun LLM lokal (`stik_model`, default `llm_model`; ±45 dtk/adegan, di-cache di `cache/stik`).
    Uji 2026-11-18: qwen2.5:7b & gemma2:9b sering tidak nyambung, jadi default tetap otomatis.
  - Cerita manual: isi `adegan[i]["cerita"]` = daftar babak (format sama dengan JSON LLM) di project.json.
  - **Adab & akurasi**: hanya orang biasa (tidak ada Nabi/Rasul/sahabat/malaikat), wanita berhijab & gamis, peluk/salaman hanya sesama jenis
    atau suami-istri, tanpa tanda benar/salah di cerita. Kata di **kalimat tanya** ("…langsung batal?") tidak dicap/diwarnai sebagai jawaban;
    idiom "salah satu" bukan kata hukum.
- Backup sebelum fitur ini: `*.bak_stik`.

## Update 2026-11-19: semua ucapan diperagakan + subtitle hologram tunggal
- **Cerita per anak kalimat** (`aw_stik.clause_beats`): narasi dipecah per anak kalimat (tanda baca, jeda, kata sambung, maks 5 kata)
  dan SETIAP potongan jadi babak stickman: kata aksi diperagakan (wudhu, makan, ngupil…), syarat (jika/selama) → berpikir dengan
  balon pikiran, sebab → menunjuk + lampu, jadi/intinya → paham, tidak batal/boleh → senang, batal/jangan → menolak, pertanyaan →
  aksinya diperagakan + lawan main bertanya-tanya, penegasan (penting/ingat) → menunjuk + tanda seru, lainnya → saling menjelaskan
  bergantian. **Balon bicara/pikiran** berisi gambar benda yang disebut (hidung, bulan puasa, buku, sabun…). Kalimat yang memuat aksi +
  hukum dipecah dua (peragakan aksinya dulu). Gerak antar babak menyambung halus.
- **Nuansa beda tiap video** (dipilih dari judul): cerah, senja, malam, hujan, pastel, komik (halftone + garis aksi), gugur
  — warna, partikel (kilau, debu emas, kunang-kunang, hujan/tetes kaca, kelopak, daun) dan latar malam.
- **Subtitle hologram tunggal** (`aw_holo.HoloSubA`): subtitle kertas dimatikan bila hologram = "Semua kata". Satu panel hologram per
  potongan kalimat di tengah layar; kalimat tampil redup, tiap kata menyala tepat saat diucapkan dengan efek bergantian, kata yang sedang
  diucapkan paling terang + garis sorot. Stiker kata di adegan cerita diganti balon tokoh (stempel tetap).
- Cerita manual (`adegan[i].cerita`) atau `stik_llm` tetap memakai babak per kata pemicu. Backup sebelum update: `*.bak_sub`.

## Update 2026-11-19 (b): render paralel + shot ala editor
- **Render paralel** (`aw_render._render_range` / `--worker`): frame dibagi ke beberapa proses (default inti CPU − 2, maks 8;
  config `render_workers`), disambung tanpa encode ulang. Video 79 dtk: ±700 dtk → ±170 dtk.
- **Jenis shot cerita** (`aw_stik._shots`): close-up anatomi kepala samping (hidung luar/dalam/batang/pangkal, mulut/tenggorokan,
  telinga, mata) dengan label yang muncul saat katanya diucapkan + jari bergerak; shot kajian (ustadz/ulama + kitab, tokoh menyimak)
  untuk ulama/ustadz/kajian/mazhab; shot bayangan (awan pikiran berisi adegan kecil) untuk jika/selama/sengaja/tindakan;
  insert benda besar; pose `lapar` untuk orang berpuasa. Potongan per satuan makna (≥0.9 dtk, maks 6 kata); shot sama berurutan
  digabung. Aksi pokok video (`topic_action`) dipakai untuk "tindakan tersebut". Backup: `*.bak_par`, `aw_stik.py.bak_shot`.
