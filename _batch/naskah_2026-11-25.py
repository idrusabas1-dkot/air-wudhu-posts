"""Naskah harian 2026-11-25 (3 tema fiqih sholat: sayyidina saat tahiyat, imam lupa surat pendek, menoleh saat sholat).
   python _batch/naskah_2026-11-25.py            # cek kutipan
   python _batch/naskah_2026-11-25.py --save     # simpan + approve
   python _batch/naskah_2026-11-25.py --render 2026-11-25 fiqih_sholat
"""
import sys
sys.path.insert(0, r"I:\AG\air-wudhu"); sys.path.insert(0, r"I:\AG\air-wudhu\_batch")
from kisah_tools import *

# ======================================================================== 1. SAYYIDINA SAAT TAHIYAT
N1 = {
 "pid": "20261124_204324_mengucapkan-sayyidina-dalam-sh",
 "slug": "sayyidina_saat_tahiyat",
 "judul_pendek": "Baca sayyidina saat tahiyat, dilarang?",
 "judul": "Mengucapkan \"Sayyidina\" dalam sholawat tahiyat itu dilarang?",
 "deskripsi": "Kisah ilustrasi: lafaz shalawat yang diajarkan Nabi, pendapat yang tidak menambahkan sayyidina, pendapat Syafi'iyah bahwa menambahkannya lebih utama sebagai adab, dan status riwayat larangannya.",
 "hashtag": ["#AirWudhu", "#NgajiSantai", "#Fiqih", "#Sholat", "#Tahiyat"],
 "adegan": [
  {"tipe": "kisah", "narasi": "Fahri kaget. Kata temannya, membaca sayyidina dalam shalawat tahiyat itu dilarang. Padahal sejak kecil ia selalu membacanya. Benarkah dilarang?",
   "judul": "Baca *sayyidina* saat tahiyat dilarang?", "kunci": ["sayyidina", "dilarang"],
   "shot": shot("musholla", "dorong", [tok("pria", "kaget")]),
   "kartu": [ilus("Fahri"), K("balon", "Sayyidina dilarang?", "kiri", pada="dilarang", pos=(400, 960))]},
  {"tipe": "kisah", "narasi": "Yang tidak menambahkannya berpegang pada hadits. Saat sahabat bertanya cara bershalawat, Rasulullah mengajarkan lafaz tanpa sayyidina.",
   "kunci": ["tanpa"],
   "shot": shot("kitab", "dorong"),
   "kartu": [K("hadits", "Ucapkanlah Allâhumma shalli ‘alâ Muhammad.",
               "HR. Muslim", "Hadits", "jatim.nu.or.id", pada="Rasulullah")]},
  {"tipe": "kisah", "narasi": "Karena itu, Majelis Tarjih Muhammadiyah memilih tidak menambahkan sayyidina di dalam shalat.", "kunci": ["Tarjih"],
   "shot": shot("kitab", "geser", fokus=(450, 1250)),
   "kartu": [K("pendapat", "Dengan demikian, menambahkan kata “sayyidina” dalam shalat adalah perbuatan yang tidak ada dasarnya sama sekali. Oleh karenanya menambahkan kata “sayyidina” tidak perlu dilakukan.",
               "Majelis Tarjih Muhammadiyah", "Tidak ditambah", "web.suaramuhammadiyah.id", pada="Majelis")]},
  {"tipe": "kisah", "narasi": "Al-Hafizh Ibnu Hajar al-Asqalani juga berpendapat, mengikuti lafaz shalawat yang diajarkan Nabi lebih didahulukan.",
   "kunci": ["Ibnu Hajar"],
   "shot": shot("kitab", "dorong"),
   "kartu": [K("pendapat", "Benar, mengikuti lafadz shalawat yang ma’tsur (sesuai dalil) itu lebih didahulukan.",
               "Al-Hafizh Ibnu Hajar", "Ikuti lafaz", "konsultasisyariah.com", pada="Ibnu")]},
  {"tipe": "kisah", "narasi": "Sebaliknya, ulama Syafi'iyah menilai menambahkan sayyidina justru lebih utama, karena termasuk adab kepada Rasulullah.",
   "kunci": ["lebih utama", "adab"],
   "shot": shot("musholla", "geser", [tok("pria", "mikir")]),
   "kartu": [K("pendapat", "Dari sini dapat dipahami bersama bahwa menambahkan lafadz sayyidina saat membaca nama Nabi Muhammad, termasuk dalam bacaan tahiyyat shalat itu hukumnya boleh, bahkan sangat utama karena termasuk tata krama/ adab terhadap Rasulullah yang merupakan perintah agama.",
               "Hasyiyah al-Jamal", "Lebih utama", "jatim.nu.or.id", pada="Sebaliknya")]},
  {"tipe": "kisah", "narasi": "Dasarnya, Rasulullah sendiri bersabda bahwa beliau adalah sayyid anak Adam pada hari kiamat.", "kunci": ["sayyid"],
   "shot": shot("kitab", "dorong"),
   "kartu": [K("hadits", "Saya adalah sayyid (penghulu) anak Adam pada hari kiamat.",
               "HR. Muslim", "Hadits", "jatim.nu.or.id", pada="Dasarnya")]},
  {"tipe": "kisah", "narasi": "Lalu riwayat larangan, jangan mengucapkan sayyidina kepadaku dalam shalat? Imam as-Sakhawi dan ulama lain menilainya tidak ada asalnya, bahkan palsu.",
   "kunci": ["palsu"],
   "shot": shot("kitab", "turun", fokus=(450, 1200)),
   "kartu": [K("pendapat", "Melihat kepada pendapat sebahagian ulama’ di atas, kami juga cenderung kepada hadith tersebut adalah mawdhu’ dan tiada asal baginya .",
               "Mufti Wilayah Persekutuan", "Status riwayat", "muftiwp.gov.my", pada="larangan"),
             K("label", "dinilai tidak ada asalnya", "biru", pada="palsu", pos=(540, 900))]},
  {"tipe": "kisah", "narasi": "Jadi, masalah ini luas. Yang tidak menambah, berpegang pada lafaz Nabi. Yang menambah, beradab kepada Nabi. Keduanya baik.",
   "kunci": ["Keduanya baik"],
   "shot": shot("kitab", "dorong"),
   "kartu": [K("kutipan", "Begitu juga barangsiapa yang ingin menambahnya juga tidak menjadi masalah kerana ia termasuk di dalam bab beradab dengan Nabi SAW dan keduanya adalah baik.",
               "Mufti Wilayah Persekutuan", sumber="muftiwp.gov.my", pada="luas"),
             K("label", "keduanya baik", "hijau", pada="Keduanya", pos=(540, 900))]},
  {"tipe": "kisah", "narasi": "Fahri pun tenang. Ia tetap membaca sayyidina, dan tetap menghormati temannya yang tidak membacanya.", "kunci": ["menghormati"],
   "shot": shot("musholla", "mundur", [tok("pria", "lega")]),
   "kartu": [ilus("Fahri")]},
  {"tipe": "penutup", "narasi": "Saat tahiyat, kamu membaca sayyidina atau tidak? Tulis di komentar, ya.",
   "tanya": "Saat tahiyat kamu baca?", "a": "Pakai sayyidina", "b": "Tanpa sayyidina"},
 ]}

# ======================================================================== 2. IMAM LUPA SURAT PENDEK
N2 = {
 "pid": "20261124_204324_imam-lupa-baca-surat-pendek-ma",
 "slug": "imam_lupa_surat_pendek",
 "judul_pendek": "Imam lupa surat pendek, makmum menegur?",
 "judul": "Imam lupa baca surat pendek, makmum harus mengingatkan?",
 "deskripsi": "Kisah ilustrasi: Al-Fatihah rukun, surat setelahnya sunnah dan tidak disunnahkan sujud sahwi bila ditinggalkan, plus cara makmum mengingatkan imam yang lupa (tasbih dengan niat dzikir).",
 "hashtag": ["#AirWudhu", "#NgajiSantai", "#Fiqih", "#Sholat", "#Berjamaah"],
 "adegan": [
  {"tipe": "kisah", "narasi": "Saat sholat Subuh berjamaah, imam langsung rukuk setelah Al-Fatihah, tanpa surat pendek. Yusuf bingung, haruskah ia mengingatkan imam?",
   "judul": "Imam *lupa surat*, makmum harus menegur?", "kunci": ["rukuk", "mengingatkan"],
   "shot": shot("musholla", "dorong", [tok("pria", "mikir", baju=BIRU)]),
   "kartu": [ilus("Yusuf"), K("balon", "Imamnya lupa surat?", "kiri", pada="bingung", pos=(400, 960))]},
  {"tipe": "kisah", "narasi": "Al-Fatihah adalah rukun shalat. Tanpanya, shalat tidak sah.", "kunci": ["rukun"],
   "shot": shot("kitab", "dorong"),
   "kartu": [K("kutipan", "Surat Al-Fatihah merupakan rukun dalam melaksanakan shalat. Sehingga tidak sah shalat seseorang jika tidak membacanya.",
               "NU Online Jakarta", sumber="jakarta.nu.or.id", pada="rukun")]},
  {"tipe": "kisah", "narasi": "Sedangkan surat pendek bukan rukun. Kata Abu Hurairah, siapa membaca Al-Fatihah, itu sudah cukup. Yang menambah, lebih baik.",
   "kunci": ["cukup", "lebih baik"],
   "shot": shot("kitab", "geser", fokus=(450, 1250)),
   "kartu": [K("hadits", "barang siapa yang membaca Umm al-Kitab (Al-Fatihah), maka sungguh telah cukup baginya, dan barang siapa menambahkan, maka itu adalah lebih baik.",
               "HR. Muslim", "Atsar Abu Hurairah", "jakarta.nu.or.id", pada="Abu")]},
  {"tipe": "kisah", "narasi": "Maka membaca surat setelah Al-Fatihah hukumnya sunnah. Kalau ditinggalkan, tidak disunnahkan sujud sahwi.",
   "kunci": ["sunnah", "sujud sahwi"],
   "shot": shot("kitab", "dorong"),
   "kartu": [K("pendapat", "Membaca surah al-Qur'an setelah al-Fatihah, hukumnya sunnah. Bila ditinggalkan maka tidak disunnahkan sujud sahwi.",
               "NU Online", "Sunnah", "islam.nu.or.id", pada="Maka"),
             K("label", "tanpa sujud sahwi", "hijau", pada="ditinggalkan", pos=(540, 900))]},
  {"tipe": "kisah", "narasi": "Beda dengan tasyahud awal. Kalau itu yang tertinggal, disunnahkan sujud sahwi.", "kunci": ["tasyahud awal"],
   "shot": shot("kitab", "turun", fokus=(450, 1200)),
   "kartu": [K("kutipan", "Sedangkan tasyahhud awal bagi shalat yang lebih dari 2 raka'at hukumnya sunnah, sehingga bisa saja ditinggalkan, tetapi disunnahkan sujud sahwi, baik ditinggalkan karena lupa maupun sengaja.",
               "NU Online", sumber="islam.nu.or.id", pada="tasyahud")]},
  {"tipe": "kisah", "narasi": "Meski begitu, ulama tetap menganjurkan surat dibaca. Meninggalkannya dimakruhkan, demi menjaga pendapat ulama yang mewajibkannya.",
   "kunci": ["dimakruhkan"],
   "shot": shot("kitab", "dorong"),
   "kartu": [K("pendapat", "Dan dimakruhkan tidak membaca surat demi menjaga pendapat ulama yang mewajibkan membaca surat setelah Al-Fatihah",
               "Fathul Mu'in", "Makruh ditinggal", "lampung.nu.or.id", pada="dimakruhkan")]},
  {"tipe": "kisah", "narasi": "Kalau imam lupa, misalnya lupa rakaat, makmum laki-laki mengingatkan dengan tasbih, dan perempuan menepuk tangan.",
   "kunci": ["tasbih", "menepuk"],
   "shot": shot("musholla", "geser", [tok("pria", "dengar", baju=BIRU)]),
   "kartu": [K("hadits", "Mengucapkan tasbih itu bagi laki-laki dan menepuk tangan itu bagi perempuan .",
               "HR. Bukhari & Muslim", "Hadits", "rumaysho.com", pada="tasbih")]},
  {"tipe": "kisah", "narasi": "Tasbihnya diniatkan dzikir. Kalau niatnya hanya mengingatkan, shalat makmum itu dianggap batal.", "kunci": ["dzikir", "batal"],
   "shot": shot("kitab", "dorong"),
   "kartu": [K("kutipan", "jika seorang ma’mum dalam jamaah shalat laki-laki mengingatkan imam dengan cara bertasbih dengan niat mengingatkan saja tanpa ada niat dzikir kepada Allah, maka shalatnya ma’mum tersebut dianggap batal.",
               "NU Online", sumber="islam.nu.or.id", pada="niatnya")]},
  {"tipe": "kisah", "narasi": "Yusuf pun lega. Surat pendek hanya sunnah, jadi shalat berjamaahnya tetap sah.", "kunci": ["tetap sah"],
   "shot": shot("musholla", "mundur", [tok("pria", "lega", baju=BIRU)]),
   "kartu": [ilus("Yusuf"), K("kutipan", "Sedangkan membaca surat pendek bukan bagian dari rukun shalat. Sehingga seseorang boleh tidak membacanya.",
               "NU Online Jakarta", sumber="jakarta.nu.or.id", pada="sunnah")]},
  {"tipe": "penutup", "narasi": "Kalau imam lupa surat pendek, kamu biasanya bagaimana? Tulis di komentar, ya.",
   "tanya": "Imam lupa surat pendek?", "a": "Diam saja", "b": "Bertasbih"},
 ]}

# ======================================================================== 3. MENOLEH SAAT SHOLAT
N3 = {
 "pid": "20261124_204324_menoleh-sedikit-saat-sholat-la",
 "slug": "menoleh_saat_sholat",
 "judul_pendek": "Menoleh sedikit saat sholat, batal?",
 "judul": "Menoleh sedikit saat sholat langsung membatalkan sholat?",
 "deskripsi": "Kisah ilustrasi: hadits menoleh adalah copetan setan, hukumnya makruh, yang membatalkan adalah memalingkan dada dari kiblat, melirik tidak mengapa, dan bolehnya menoleh karena keperluan.",
 "hashtag": ["#AirWudhu", "#NgajiSantai", "#Fiqih", "#Sholat", "#Khusyuk"],
 "adegan": [
  {"tipe": "kisah", "narasi": "Saat sholat, Hafiz mendengar suara keras di sampingnya. Spontan ia menoleh sedikit. Apakah sholatnya langsung batal?",
   "judul": "Menoleh sedikit, sholat *batal?*", "kunci": ["menoleh", "batal"],
   "shot": shot("musholla", "dorong", [tok("pria", "kaget", baju=HIJAU)]),
   "kartu": [ilus("Hafiz"), K("balon", "Batal nggak, ya?", "kiri", pada="batal", pos=(400, 960))]},
  {"tipe": "kisah", "narasi": "Aisyah pernah bertanya kepada Rasulullah tentang menoleh dalam shalat. Jawab beliau, itu copetan setan dari shalat seorang hamba.",
   "kunci": ["copetan"],
   "shot": shot("kitab", "dorong"),
   "kartu": [K("hadits", "Ia adalah copetan yang dilakukan setan pada shalat seorang hamba.",
               "HR. Bukhari no. 751", "Hadits", "rumaysho.com", pada="Aisyah")]},
  {"tipe": "kisah", "narasi": "Hukumnya makruh. Jumhur ulama menyebutnya makruh tanzih.", "kunci": ["makruh"],
   "shot": shot("kitab", "geser", fokus=(450, 1250)),
   "kartu": [K("pendapat", "Para ulama sepakat bahwa menoleh dalam shalat termasuk perbuatan makruh (terlarang). Jumhur ulama mengatakan bahwa hukumnya itu makruh tanzih .",
               "Syarah Bulughul Maram", "Makruh", "rumaysho.com", pada="Hukumnya")]},
  {"tipe": "kisah", "narasi": "Disebut copetan setan karena menoleh mengurangi kekhusyukan kita dalam shalat.", "kunci": ["kekhusyukan"],
   "shot": shot("musholla", "geser", [tok("pria", "mikir", baju=HIJAU)]),
   "kartu": [K("kutipan", "Disebut copetan yang dilakukan setan pada seorang hamba dalam shalat karena menoleh seperti itu mengurangi kekhusyukan kita dalam shalat.",
               "Ustadz Muhammad Abduh Tuasikal", sumber="rumaysho.com", pada="Disebut")]},
  {"tipe": "kisah", "narasi": "Yang membatalkan adalah memalingkan dada, sampai badan tidak lagi menghadap kiblat.", "kunci": ["dada", "kiblat"],
   "shot": shot("kitab", "dorong"),
   "kartu": [K("pendapat", "Adapun jika memalingkan dada lantas menjauh dari arah kiblat, shalatnya batal karena meninggalkan rukun menghadap kiblat.",
               "Rumaysho", "Batal", "rumaysho.com", pada="membatalkan"),
             K("label", "dada berpaling dari kiblat", "merah", pada="dada", pos=(540, 900))]},
  {"tipe": "kisah", "narasi": "Sedangkan melirik dengan mata, tidak mengapa.", "kunci": ["melirik"],
   "shot": shot("kitab", "turun", fokus=(450, 1200)),
   "kartu": [K("kutipan", "Adapun mencuri pandangan dengan mata, tidaklah mengapa.",
               "Rumaysho", sumber="rumaysho.com", pada="melirik")]},
  {"tipe": "kisah", "narasi": "Buya Yahya menjelaskan, menoleh tidak membatalkan, asal tidak tiga kali berturut-turut, karena leher termasuk anggota besar.",
   "kunci": ["tiga kali"],
   "shot": shot("kitab", "dorong"),
   "kartu": [K("kutipan", "Menoleh ke kiri dan ke kanan tidak membatalkan sholat asalkan tidak melakukan gerakan tiga kali berturut-turut,",
               "Buya Yahya", sumber="liputan6.com", pada="Buya")]},
  {"tipe": "kisah", "narasi": "Kalau ada keperluan, menoleh dibolehkan. Saat sakit, Rasulullah pernah menoleh untuk memberi isyarat kepada makmum.",
   "kunci": ["keperluan"],
   "shot": shot("kitab", "geser", fokus=(450, 1250)),
   "kartu": [K("hadits", "Kemudian beliau menoleh dan melihat kami berdiri. Kemudian beliau mengisyaratkan kepada kami (untuk duduk), lalu kami pun duduk.",
               "Hadits Jabir", "Ada keperluan", "almanhaj.or.id", pada="Saat")]},
  {"tipe": "kisah", "narasi": "Tapi jangan dibiasakan. Pesan Buya Yahya, jangan mentang-mentang tidak batal, lalu sholatnya tolah-toleh.",
   "kunci": ["tolah-toleh"],
   "shot": shot("musholla", "dorong", [tok("pria", "dengar", baju=HIJAU)]),
   "kartu": [K("kutipan", "Sholat itu jangan tolah-toleh. Jangan mentang-mentang tidak batal, lalu nanti sholatnya tolah-toleh,",
               "Buya Yahya", sumber="liputan6.com", pada="Pesan")]},
  {"tipe": "kisah", "narasi": "Hafiz lega, sholatnya tidak batal. Mulai sekarang, pandangannya ia jaga ke tempat sujud.", "kunci": ["tempat sujud"],
   "shot": shot("musholla", "mundur", [tok("pria", "sholat_gerak", baju=HIJAU)]),
   "kartu": [ilus("Hafiz")]},
  {"tipe": "penutup", "narasi": "Kamu pernah spontan menoleh saat sholat? Tulis di komentar, ya.",
   "tanya": "Pernah menoleh saat sholat?", "a": "Pernah", "b": "Tidak pernah"},
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
