# air-wudhu-posts
Gambar posting harian halaman Facebook Air-Wudhu.
- `queue.json`: antrean 90 konten tema "Koreksi Mitos & Salah Kaprah Ibadah" (dari Konten_Plan_Islam_FB_30_Hari_90_Video.xlsx; isi dan sumber ditulis ringkas, mohon direview). `posted.json`: id yang sudah terbit.
- `scripts/make_post.py out.png "Judul" "Isi" "Sumber"`: membuat gambar 1080x1080 dengan banner Air-Wudhu (assets/banner.jpg) di bagian bawah.
- `images/`: gambar publik yang dipakai Facebook lewat URL raw.githubusercontent.com.

## DKOT Coffee (Instagram @dkot_coffee)
- `dkot/stories/{jam}-{varian}.jpg`: story promo 1080x1920 untuk jam 07,10,12,15,18,20 WIB, 3 varian per jam (rotasi harian). Ajakan order di ShopeeFood & GrabFood + "Klik link di bio".
- `scripts/make_dkot_story.py dkot/stories`: membuat ulang semua gambar.
- `dkot/menu/NN-nama.jpg`: 12 story menu (foto gelas asli DKOT, latar dedaunan). Ini yang dipakai jadwal sejak 20 Nov 2026; `dkot/stories` tidak dipakai lagi.
- `dkot/cutouts/`: potongan gelas tanpa latar. `python3 scripts/make_menu_story.py dkot/cutouts dkot/menu` membuat ulang gambar menu.
- v2 (20 Nov 2026 malam): `dkot/menu/` diganti versi lebih ramai (sinar, es & biji kopi melayang, stiker, linktree, area antar). Buat ulang: `cd scripts && python3 make_story_v2.py ../dkot/cutouts ../dkot/menu`.
- `dkot/reels/NN-nama.mp4`: 12 Reels 15 detik dengan musik orisinal 128 BPM (`make_beat.py`, `make_reel.py`). Caption + hashtag di `dkot/reels.json`.
