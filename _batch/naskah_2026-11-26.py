"""Naskah harian 2026-11-26 (3 tema fiqih sholat: kaos bergambar & makmum, mukena warna-warni, dagu terlihat saat pakai mukena).
   python _batch/naskah_2026-11-26.py            # cek kutipan
   python _batch/naskah_2026-11-26.py --save     # simpan + approve
   python _batch/naskah_2026-11-26.py --render 2026-11-26 fiqih_sholat
"""
import sys
sys.path.insert(0, r"I:\AG\air-wudhu"); sys.path.insert(0, r"I:\AG\air-wudhu\_batch")
from kisah_tools import *

MUKENA = [236, 236, 228]
MUKENA_WARNA = [200, 120, 170]


def wanita(aksi, jilbab=MUKENA, **kw):
    t = tok("wanita", aksi, **kw)
    t["jilbab"] = jilbab
    return t


# ======================================================================== 1. KAOS BERGAMBAR & MAKMUM
N1 = {
 "pid": "20261125_224211_sholat-pakai-kaos-bergambar-di",
 "slug": "kaos_bergambar_makmum",
 "judul_pendek": "Kaos bergambar bikin sholat makmum batal?",
 "judul": "Sholat pakai kaos bergambar di belakang bikin sholat makmum batal?",
 "deskripsi": "Kisah ilustrasi: syarat pakaian sholat (menutup aurat dan suci), hadits khamishah Abu Jahm, hukum makruh pakaian bergambar menurut ulama Syafi'iyah, gambar di punggung mengganggu jamaah belakang, dan sholat tetap sah.",
 "hashtag": ["#AirWudhu", "#NgajiSantai", "#Fiqih", "#Sholat", "#Berjamaah"],
 "adegan": [
  {"tipe": "kisah", "narasi": "Saat Isya berjamaah, Raka berdiri di belakang jamaah yang memakai kaos bergambar besar di punggung. Matanya terus tertuju ke gambar itu. Batalkah sholatnya?",
   "judul": "Kaos bergambar, sholat makmum *batal?*", "kunci": ["kaos bergambar", "batal"],
   "shot": shot("musholla", "dorong", [tok("pria", "kaget")]),
   "kartu": [ilus("Raka"), K("balon", "Sholatku batal?", "kiri", pada="Batalkah", pos=(400, 960))]},
  {"tipe": "kisah", "narasi": "Syarat utama pakaian sholat ada dua: menutup aurat, dan suci dari najis.",
   "kunci": ["menutup aurat", "suci"],
   "shot": shot("kitab", "dorong"),
   "kartu": [K("kutipan", "Dalam fiqih, syarat utama pakaian yang digunakan untuk shalat adalah mampu menutup aurat dan suci dari najis.",
               "NU Online", sumber="islam.nu.or.id", pada="Syarat")]},
  {"tipe": "kisah", "narasi": "Rasulullah pernah sholat memakai pakaian bercorak. Setelahnya, beliau minta pakaian itu dikembalikan kepada Abu Jahm, karena membuat beliau lalai.",
   "kunci": ["lalai"],
   "shot": shot("kitab", "geser", fokus=(450, 1250)),
   "kartu": [K("hadits", "Bawalah baju ini dan kembalikan kepada Abu Jahm, berikan pakaian anbijaniyahnya (pakaian wol yang tidak bergambar) kepadaku. Pakaian ini telah membuat aku lalai dalam salatku.",
               "HR. Bukhari", "Hadits", "mozaik.inilah.com", pada="Rasulullah")]},
  {"tipe": "kisah", "narasi": "Karena itu, Imam An-Nawawi menyebut sholat dengan pakaian bergambar hukumnya makruh.",
   "kunci": ["makruh"],
   "shot": shot("kitab", "dorong"),
   "kartu": [K("pendapat", "Adapun pakaian yang di dalamnya terdapat gambar-gambar, salib, atau sesuatu yang mengalihkan perhatian, maka dimakruhkan shalat dengan mengenakannya",
               "Al-Majmu', Imam An-Nawawi", "Makruh", "islam.nu.or.id", pada="Nawawi")]},
  {"tipe": "kisah", "narasi": "Makruh, tapi tidak batal. Selama pakaiannya suci, sholat pemakainya tetap sah.",
   "kunci": ["tetap sah"],
   "shot": shot("kitab", "turun", fokus=(450, 1200)),
   "kartu": [K("kutipan", "Hal ini secara hukum fiqih tidak dihukumi batal sholatnya dan tetap sah karena selama pakaian yang dikenakan itu suci dan bersih itu sudah memenuhi syarat sahnya shalat.",
               "NU Online Jateng", sumber="jateng.nu.or.id", pada="Makruh"),
             K("label", "sah, tapi makruh", "hijau", pada="tetap", pos=(540, 900))]},
  {"tipe": "kisah", "narasi": "Gambar di punggung memang bisa mengganggu jamaah di belakangnya, walau pemakainya sendiri tidak melihatnya.",
   "kunci": ["punggung", "mengganggu"],
   "shot": shot("musholla", "geser", [tok("pria", "mikir")]),
   "kartu": [K("kutipan", "Gambar pada bagian belakang pakaian dapat mengganggu jamaah yang berada di belakang pemakainya, meskipun orang yang mengenakan jersey tersebut tidak melihatnya.",
               "Ustadz Muhammad Zainul Millah", sumber="islam.nu.or.id", pada="punggung")]},
  {"tipe": "kisah", "narasi": "Bagi makmum yang melihatnya, Ibnu Hajar al-Haitami menyebut sholatnya makruh.",
   "kunci": ["makmum", "makruh"],
   "shot": shot("kitab", "dorong"),
   "kartu": [K("pendapat", "Maka pendapat yang lebih kuat adalah, apabila hal tersebut berada dalam penglihatan seseorang, maka shalatnya dimakruhkan.",
               "Ibnu Hajar al-Haitami", "Makmum", "islam.nu.or.id", pada="Ibnu")]},
  {"tipe": "kisah", "narasi": "Tapi tidak batal. Kata Imam An-Nawawi, sholat tetap sah walau pikiran terganggu hal di luar sholat. Ini kesepakatan para ulama fiqih.",
   "kunci": ["kesepakatan"],
   "shot": shot("kitab", "geser", fokus=(450, 1250)),
   "kartu": [K("kutipan", "Dalam hal ini, shalat tetap sah meskipun terdapat gangguan pikiran terhadap hal yang tidak berkaitan dengan shalat. Ini adalah kesepakatan para ulama fiqih.",
               "Imam An-Nawawi", sumber="islam.nu.or.id", pada="Nawawi"),
             K("label", "makmum tetap sah", "hijau", pada="kesepakatan", pos=(540, 900))]},
  {"tipe": "kisah", "narasi": "Kalau terlanjur memakai kaos bergambar, ustadz Erick Yusuf menyarankan gambarnya ditutup jaket, atau bajunya dibalik.",
   "kunci": ["jaket", "dibalik"],
   "shot": shot("kitab", "dorong"),
   "kartu": [K("kutipan", "ustadz Erick menganjurkan agar Muslim menutupi gambar pada baju mereka dengan jaket. Alternatif lain yang bisa dilakukan adalah membalik baju tersebut agar bagian gambarnya berada di dalam dan tidak terlihat.",
               "Ustadz Erick Yusuf", sumber="ameera.republika.co.id", pada="jaket")]},
  {"tipe": "kisah", "narasi": "Raka lega, sholatnya tetap sah. Sejak itu, ia memilih baju polos saat ke musholla, dan menjaga pandangan ke tempat sujud.",
   "kunci": ["baju polos"],
   "shot": shot("musholla", "mundur", [tok("pria", "lega")]),
   "kartu": [ilus("Raka")]},
  {"tipe": "penutup", "narasi": "Kamu pernah sholat pakai kaos bergambar? Tulis di komentar, ya.",
   "tanya": "Sholat pakai kaos bergambar?", "a": "Pernah", "b": "Selalu ganti baju"},
 ]}

# ======================================================================== 2. MUKENA WARNA-WARNI
N2 = {
 "pid": "20261125_224211_sholat-memakai-mukena-warna-wa",
 "slug": "mukena_warna_warni",
 "judul_pendek": "Mukena warna-warni, sholat tidak sah?",
 "judul": "Sholat memakai mukena warna-warni itu tidak sah?",
 "deskripsi": "Kisah ilustrasi: syarat sah pakaian sholat wanita (menutup aurat dan suci), hasil Bahtsul Masail FMP3 Jawa Timur di Lirboyo 2024 tentang mukena bermotif, kapan menjadi makruh, dan mukena tipis yang justru membuat sholat tidak sah.",
 "hashtag": ["#AirWudhu", "#NgajiSantai", "#Fiqih", "#Sholat", "#Muslimah"],
 "adegan": [
  {"tipe": "kisah", "narasi": "Nisa mendapat hadiah mukena warna-warni. Tapi kata tetangganya, mukena harus putih. Kalau warna-warni, sholatnya tidak sah. Benarkah?",
   "judul": "Mukena warna-warni, sholat *tidak sah?*", "kunci": ["warna-warni", "tidak sah"],
   "shot": shot("teras", "dorong", [wanita("kaget", MUKENA_WARNA)]),
   "kartu": [ilus("Nisa"), K("balon", "Harus putih?", "kiri", pada="putih", pos=(400, 960))]},
  {"tipe": "kisah", "narasi": "Bahtsul Masail NU Jombang menjelaskan, sholat sah bila penutupnya bisa menutup warna kulit aurat, dari atas, samping, depan, dan belakang.",
   "kunci": ["warna kulit"],
   "shot": shot("kitab", "dorong"),
   "kartu": [K("pendapat", "Sah apabila dapat menutup warna kulit aurot sepanjang shalat dari sisi atas, samping, depan dan belakang",
               "Bahtsul Masail NU Jombang", "Syarat sah", "jombang.nu.or.id", pada="Jombang")]},
  {"tipe": "kisah", "narasi": "Syarat berikutnya, pakaiannya suci. Bahkan sholat dengan gamis tanpa mukena pun boleh, asal syarat itu terpenuhi. Warna putih tidak termasuk syaratnya.",
   "kunci": ["suci", "gamis"],
   "shot": shot("kitab", "geser", fokus=(450, 1250)),
   "kartu": [K("kutipan", "memakai baju gamis untuk shalat sebagaimana pemakaian mukena diperbolehkan asal memenuhi syarat atau kriteria syara sebagaimana keterangan tersebut di atas",
               "NU Online Jatim", sumber="jatim.nu.or.id", pada="gamis")]},
  {"tipe": "kisah", "narasi": "Soal mukena bermotif, Bahtsul Masail pesantren putri se-Jawa Timur di Lirboyo tahun 2024 memutuskan: pada dasarnya boleh.",
   "kunci": ["boleh"],
   "shot": shot("kitab", "dorong"),
   "kartu": [K("pendapat", "Pada dasarnya memakai perlengkapan shalat sebagaimana dalam deskripsi diperbolehkan, selama gambar, corak atau variasi warnanya tidak berpotensi mengganggu konsentrasi shalat.",
               "Bahtsul Masail FMP3 Jatim", "Boleh", "islam.nu.or.id", pada="Lirboyo"),
             K("label", "pada dasarnya boleh", "hijau", pada="boleh", pos=(540, 900))]},
  {"tipe": "kisah", "narasi": "Menjadi makruh bila motif atau warnanya mencolok, sampai mengalihkan perhatian.",
   "kunci": ["makruh", "mencolok"],
   "shot": shot("teras", "geser", [wanita("mikir", MUKENA_WARNA)]),
   "kartu": [K("kutipan", "Kemakruhan berlaku jika motif atau warna mukena berpotensi mengalihkan perhatian, seperti motif mencolok atau gambar yang aneh.",
               "NU Online Jabar", sumber="jabar.nu.or.id", pada="makruh")]},
  {"tipe": "kisah", "narasi": "Dasarnya, Rasulullah mengecam orang yang mengangkat pandangan ke langit saat sholat, karena mengganggu kekhusyukan.",
   "kunci": ["langit"],
   "shot": shot("kitab", "turun", fokus=(450, 1200)),
   "kartu": [K("hadits", "Hendaknya mereka berhenti dari hal itu, atau (jika tidak) niscaya penglihatan mereka tercerabut secara cepat.",
               "HR. Al-Bukhari", "Hadits", "islam.nu.or.id", pada="langit")]},
  {"tipe": "kisah", "narasi": "Meski makruh, sholatnya tetap sah. Kata Imam An-Nawawi, ini kesepakatan para ulama fiqih.",
   "kunci": ["tetap sah"],
   "shot": shot("kitab", "dorong"),
   "kartu": [K("kutipan", "Dalam hal ini, shalat tetap sah meskipun terdapat gangguan pikiran terhadap hal yang tidak berkaitan dengan shalat. Ini adalah kesepakatan para ulama fiqih.",
               "Imam An-Nawawi", sumber="islam.nu.or.id", pada="Nawawi")]},
  {"tipe": "kisah", "narasi": "Yang justru membuat tidak sah adalah mukena tipis, sampai warna kulit terlihat dari baliknya.",
   "kunci": ["tipis"],
   "shot": shot("kitab", "geser", fokus=(450, 1250)),
   "kartu": [K("kutipan", "Jika kainnya tipis atau tenunannya jarang-jarang, sehingga dapat menampakkan apa yang di bawahnya atau dapat menggambarkan warna kulitnya hingga tampak kulit pemakai yang cerah atau kemerah-merahan, maka kain tersebut tidak memenuhi syarat untuk digunakan shalat.",
               "Al-Fiqh al-Islami, Wahbah Zuhaili", sumber="jatim.nu.or.id", pada="tipis"),
             K("label", "mukena tipis: tidak sah", "merah", pada="tipis", pos=(540, 900))]},
  {"tipe": "kisah", "narasi": "Nisa lega. Mukenanya tebal dan suci. Untuk menjaga kualitas sholat, ia memilih motif yang sederhana dan tidak mencolok.",
   "kunci": ["sederhana"],
   "shot": shot("musholla", "mundur", [wanita("lega", MUKENA_WARNA)]),
   "kartu": [ilus("Nisa"), K("kutipan", "Namun, dalam konteks menjaga kualitas shalat, diutamakan menggunakan mukena yang sederhana dan tidak mencolok.",
               "NU Online Jabar", sumber="jabar.nu.or.id", pada="sederhana")]},
  {"tipe": "penutup", "narasi": "Mukena favoritmu yang mana? Tulis di komentar, ya.",
   "tanya": "Mukena favoritmu?", "a": "Putih polos", "b": "Bermotif kalem"},
 ]}

# ======================================================================== 3. DAGU TERLIHAT SAAT PAKAI MUKENA
N3 = {
 "pid": "20261125_224211_dagu-wanita-terlihat-sedikit-s",
 "slug": "dagu_terlihat_mukena",
 "judul_pendek": "Dagu terlihat saat pakai mukena, batal?",
 "judul": "Dagu wanita terlihat sedikit saat pakai mukena bikin sholat batal?",
 "deskripsi": "Kisah ilustrasi: aurat wanita dalam sholat, batas wajah menurut Imam An-Nawawi (dagu depan termasuk wajah, bawah dagu bukan), hukum terbukanya bawah dagu menurut mazhab Syafi'i dan mazhab lain, soal shalat yang sudah lewat, dan solusi praktis memakai mukena.",
 "hashtag": ["#AirWudhu", "#NgajiSantai", "#Fiqih", "#Sholat", "#Muslimah"],
 "adegan": [
  {"tipe": "kisah", "narasi": "Selesai sholat, Salma becermin. Ternyata karet mukenanya hanya di bawah dagu, dan dagunya terlihat. Apakah sholatnya batal?",
   "judul": "Dagu terlihat saat pakai mukena, *batal?*", "kunci": ["dagu", "batal"],
   "shot": shot("musholla", "dorong", [wanita("kaget")]),
   "kartu": [ilus("Salma"), K("balon", "Daguku kelihatan!", "kiri", pada="terlihat", pos=(400, 960))]},
  {"tipe": "kisah", "narasi": "Aurat wanita dalam sholat adalah seluruh tubuh, kecuali wajah dan kedua telapak tangan.",
   "kunci": ["wajah", "telapak tangan"],
   "shot": shot("kitab", "dorong"),
   "kartu": [K("pendapat", "Adapun aurat perempuan merdeka adalah seluruh tubuhnya kecuali wajah dan telapak tangan hingga pergelangan.",
               "Al-Majmu', Imam An-Nawawi", "Aurat", "islam.nu.or.id", pada="Aurat")]},
  {"tipe": "kisah", "narasi": "Lalu, sampai mana batas wajah? Kata Imam An-Nawawi, sampai dagu bagian depan. Jadi dagu yang menghadap ke depan termasuk wajah.",
   "kunci": ["dagu bagian depan"],
   "shot": shot("kitab", "geser", fokus=(450, 1250)),
   "kartu": [K("kutipan", "An-Nawawi (w 676 H) menjelaskan bahwa batas wajah adalah antara tempat tumbuhnya rambut kepala pada umumnya, sampai bagian dagu yang menghadap kedepan dan dua tulang rahang, serta bagian antara dua telinga.",
               "NU Online", sumber="islam.nu.or.id", pada="batas")]},
  {"tipe": "kisah", "narasi": "Tapi bagian bawah dagu bukan wajah. Menurut mazhab Syafi'i, kalau bagian itu terbuka, sholat bisa batal, karena syarat menutup aurat tidak terpenuhi.",
   "kunci": ["bawah dagu", "batal"],
   "shot": shot("kitab", "dorong"),
   "kartu": [K("pendapat", "Berdasarkan penjelasan di atas, bagian bawah dagu bukanlah termasuk bagian dari wajah, sehingga jika bagian tersebut terbuka, maka dapat membatalkan shalat, karena syarat shalat tidak terpenuhi.",
               "Mazhab Syafi'i", "Bawah dagu", "islam.nu.or.id", pada="bawah"),
             K("label", "bawah dagu wajib tertutup", "merah", pada="Syafi'i", pos=(540, 900))]},
  {"tipe": "kisah", "narasi": "Karena itu, Ibnu Hajar al-Haitami menjelaskan, sebagian wajah dan bawah dagu wajib ditutup, agar yakin aurat benar-benar tertutup.",
   "kunci": ["wajib ditutup"],
   "shot": shot("musholla", "geser", [wanita("mikir")]),
   "kartu": [K("pendapat", "Wajib menutup sebagian dari wajah, kepala, dan bagian bawah dagu agar yakin bahwa aurat benar-benar telah tertutup.",
               "Tuhfatul Muhtaj", "Ihtiyath", "ldnucabangtuban.com", pada="Ibnu")]},
  {"tipe": "kisah", "narasi": "Bagaimana mazhab lain? Menurut Hanafiyah dan Malikiyah, terbuka bagian bawah dagu tidak membatalkan sholat.",
   "kunci": ["Hanafiyah", "Malikiyah"],
   "shot": shot("kitab", "turun", fokus=(450, 1200)),
   "kartu": [K("kutipan", "Adapun mazhab lainnya, seperti kalangan Hanafiyah dan Malikiyah, sesungguhnya terbuka bagian bawah dagu dan sesamanya bagi perempuan tidak membatalkan shalat",
               "Syekh Ismail Zain", sumber="islam.nu.or.id", pada="mazhab")]},
  {"tipe": "kisah", "narasi": "Lalu sholat yang sudah lewat karena belum tahu? Menurut fatwa Syekh Ismail Zain, tidak harus diqadha.",
   "kunci": ["diqadha"],
   "shot": shot("kitab", "dorong"),
   "kartu": [K("kutipan", "Demikian penjelasan tentang perempuan yang baru mengetahui bahwa dagu termasuk dari aurat. Ia tidak harus melakukan qadha untuk shalat yang sudah lewat.",
               "NU Online", sumber="islam.nu.or.id", pada="Ismail")]},
  {"tipe": "kisah", "narasi": "Solusinya, pakai mukena yang ada penutup dagunya. Atau pakai ciput yang menutup leher sampai ke bawah dagu, sebelum memakai mukena.",
   "kunci": ["ciput"],
   "shot": shot("kitab", "geser", fokus=(450, 1250)),
   "kartu": [K("kutipan", "jika menggunakan mukena biasa, gunakanlah ciput atau ninja yang menutupi leher hingga ke bawah dagu sebelum memakai mukena.",
               "LDNU Tuban", sumber="ldnucabangtuban.com", pada="ciput")]},
  {"tipe": "kisah", "narasi": "Kini, Salma selalu becermin sejenak sebelum takbiratul ihram, memastikan bawah dagunya tertutup.",
   "kunci": ["becermin"],
   "shot": shot("musholla", "mundur", [wanita("cek")]),
   "kartu": [ilus("Salma"), K("kutipan", "Inilah mengapa penting bagi setiap wanita untuk bercermin sejenak sebelum takbiratul ihram untuk memastikan tidak ada aurat yang tersingkap.",
               "LDNU Tuban", sumber="ldnucabangtuban.com", pada="becermin")]},
  {"tipe": "penutup", "narasi": "Mukenamu sudah menutup bawah dagu? Tulis di komentar, ya.",
   "tanya": "Mukenamu menutup bawah dagu?", "a": "Sudah", "b": "Baru mau cek"},
 ]}


NASKAH = [N1, N2, N3]

if __name__ == "__main__":
    if "--render" in sys.argv:
        i = sys.argv.index("--render")
        render([(N["pid"], N["slug"]) for N in NASKAH], sys.argv[i + 1], sys.argv[i + 2])
        sys.exit(0)
    save = "--save" in sys.argv
    bad = 0
    for N in NASKAH:
        print("##", N["judul"])
        bad += verify_and_save(N, save)
    sys.exit(1 if bad else 0)
