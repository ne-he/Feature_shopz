# Feature Store MVP — Penjelasan Lengkap & Materi Presentasi Customer

> **Satu dokumen, dua bagian:**
> - **BAGIAN A — Penjelasan Teknis** → buat presentasi ke temen Data Science & dosen. Problem → arsitektur → 23 fitur → 5 endpoint → kualitas → kenapa hemat. Istilah teknis dibiarin English, penjelasan Indonesia.
> - **BAGIAN B — Pitch untuk Customer** → buat pengguna bisnis yang **nggak ngerti ML**. Siapa target customer-nya, cara pakainya, dan kenapa ini nguntungin mereka secara nyata (bukan jargon).
>
> Tagline produk: **"One definition. Two stores. Zero skew."** (Satu definisi. Dua store. Tanpa skew.)

---

# BAGIAN A — Penjelasan Teknis (untuk tim DS & dosen)

## A0. Hook pembuka (20 detik)

> "Bayangin satu model ML yang pas dilatih akurasinya bagus, tapi pas dipakai di produksi prediksinya ngaco. Sering banget penyebabnya satu hal sepele: angka fitur yang dipakai waktu **training** beda sama waktu **serving**. Itu namanya **train/serve skew**. Project ini — sebuah **feature store** — dibangun khusus buat ngebunuh masalah itu."

## A1. Masalah yang diselesaikan

Di ML, **feature** = angka turunan dari data mentah (contoh: "berapa hari sejak user terakhir belanja"). Tiga masalah klasik:

1. **Train/serve skew** — waktu training, fitur dihitung pakai script A (pandas, batch). Waktu produksi, dihitung ulang pakai script B (real-time). Dua script gampang beda → model dapat input beda → prediksi salah, dan **diam-diam, susah ke-detect**.
2. **Duplikasi kerja** — tiap data scientist ngitung ulang fitur yang sama buat tiap model.
3. **Lambat di serving** — ngitung fitur on-the-fly tiap request itu mahal & lemot.

**Solusi feature store:** definisikan fitur **sekali**, simpan hasilnya di **dua tempat** dengan definisi yang **sama persis**.

## A2. Konsep inti: satu definisi, dua store

- **Offline store = PostgreSQL.** Nyimpen fitur dalam jumlah besar buat **melatih model** (training butuh banyak baris historis sekaligus).
- **Online store = Redis.** Nyimpen fitur **terbaru per user** buat **inference real-time** (butuh latency milidetik per request).

Dua-duanya diisi dari **pipeline yang sama** → angka di training = angka di produksi. **Skew hilang by design.**

> **Analogi buat dosen:** ini *single source of truth* buat fitur. Postgres = gudang besar (analitik/training), Redis = etalase cepat (serving).

## A3. Arsitektur end-to-end

```
CSV mentah
   │  (1) Ingestion: validasi skema, cleaning, normalisasi
   ▼
Feature Pipeline  ── menghitung 23 fitur secara batch (pandas/polars)
   │
   ├──────────────┬──────────────┐
   ▼              ▼
PostgreSQL     Redis            ← dua store, dijaga SINKRON
(offline)      (online)
   │              │
   ▼              ▼
        FastAPI REST API  ── 5 endpoint
   │
   ▼
ML Models (training + real-time inference)
```

1. **Ingestion** — baca CSV e-commerce, validasi skema, bersihin, normalisasi.
2. **Feature pipeline** — hitung 23 fitur secara batch. Tiap fitur didaftarin lewat pola **decorator + global REGISTRY**, jadi **katalog fitur otomatis kebentuk** — ga ada fitur "siluman" yang ga terdokumentasi.
3. **Dual write + sync** — hasil ditulis ke Postgres (offline) **dan** Redis (online), dijaga konsisten.
4. **Serving** — FastAPI mengekspos fitur lewat REST.
5. **Refresh harian** — scheduled job (**APScheduler**) nge-refresh fitur tiap hari, plus **drift monitoring (Evidently)** buat deteksi kalau distribusi data berubah.

## A4. 23 fitur dalam 6 kategori (inti "nilai" produk)

Tiap fitur = sinyal perilaku user yang berguna buat model (churn, rekomendasi, segmentasi, dll).

**A. RFM (Recency, Frequency, Monetary) — 5 fitur.** Kerangka klasik nilai pelanggan.
- `recency_days` — berapa hari sejak pembelian terakhir (makin kecil makin "hidup").
- `frequency_count` — total jumlah transaksi.
- `monetary_total` — total belanja seumur hidup (lifetime spend).
- `monetary_avg_per_purchase` — rata-rata nilai per order (AOV).
- `monetary_max` — transaksi terbesar sekali belanja.

**B. Behavioral — 5 fitur.** Pola & preferensi.
- `preferred_category` — kategori produk paling sering dibeli.
- `preferred_device` — device paling sering dipakai.
- `preferred_referral` — sumber traffic paling umum.
- `category_diversity_count` — jumlah kategori berbeda yang pernah dibeli.
- `product_diversity_count` — jumlah produk berbeda yang pernah dibeli.

**C. Engagement — 4 fitur.** Seberapa terlibat user.
- `avg_session_duration` — rata-rata durasi sesi (menit).
- `avg_review_score` — rata-rata skor review yang dia kasih (1–5).
- `total_reviews_given` — total review yang ditulis.
- `positive_review_ratio` — proporsi review ≥ 4 (sentimen positif).

**D. Temporal — 3 fitur.** Dimensi waktu.
- `days_since_signup` — umur akun sampai pembelian terakhir.
- `is_active_30d` — apakah login terakhir dalam 30 hari (flag aktif).
- `purchase_velocity` — rata-rata pembelian per bulan aktif (momentum).

**E. Discount — 3 fitur.** Sensitivitas harga.
- `discount_usage_rate` — proporsi pembelian yang pakai diskon.
- `avg_discount_rate` — rata-rata % diskon pada pembelian berdiskon.
- `total_savings` — total penghematan dari diskon.

**F. Demographics — 3 fitur.** Profil dasar.
- `age` — umur.
- `country` — negara terdaftar.
- `gender` — gender (self-reported).

> **Poin buat dosen:** kategorisasi ini bukan asal — RFM itu standar industri *customer analytics*, dan campuran behavioral/temporal/discount bikin fitur cukup kaya buat banyak use case (churn prediction, CLV, rekomendasi, segmentasi).

## A5. Serving layer: 5 endpoint REST (FastAPI)

| Endpoint | Fungsi |
|---|---|
| `GET /health` | Cek API + status store hidup/nggak (buat monitoring & badge live). |
| `GET /features/online/{user_id}` | **Redis dulu**, kalau miss fallback ke **PostgreSQL**. Jalur real-time, target latency milidetik. *Resilience boundary*: satu store down, sistem masih jalan. |
| `POST /features/batch` | Ambil fitur sampai **100 user** sekaligus dari online store (buat scoring batch). |
| `GET /features/offline/{user_id}` | **PostgreSQL only**, buat lookup training/analitik. |
| `GET /features/metadata` | Katalog 23 fitur dari REGISTRY (nama, deskripsi, tipe, valid range) + timestamp terakhir dihitung. |

Tiap response bawa **provenance metadata**: `computed_at`, `feature_version`, dan `source` (redis/postgres) — jadi jelas angkanya dari mana & kapan dihitung. Ada juga **timing middleware** yang nyetempel header `X-Process-Time-Ms` di tiap request.

## A6. Kualitas engineering (poin yang dosen suka)

- **Type hints + Mypy strict, Ruff + Black** → kode disiplin, ga asal.
- **Pydantic v2** buat validasi I/O → request/response ketat skemanya.
- **Testing serius** — ~177 test (unit + integration pakai **testcontainers** buat Postgres asli, **fakeredis** buat Redis), coverage tinggi, semua hijau.
- **Config terpusat** (Pydantic Settings) → ga ada credential/hardcoded path nyangkut di kode.
- **Logging terstruktur** (Loguru), error handling rapi (422 validation, 503 store down, 404 not found).
- **Drift monitoring** (Evidently) → tau kalau distribusi fitur bergeser dari waktu ke waktu.

> **Catatan jujur soal performa (sebut ini, jangan over-claim):** angka "<100ms p99" itu **target desain**, diukur in-process (TestClient, tanpa network/Redis/DB sungguhan) — **bukan benchmark produksi**.

## A7. Kesimpulan — kenapa ini HEMAT (bagian bisnis)

Feature store keliatan "infra nerd", tapi nilainya **duit**:

- **Hitung sekali, pakai banyak kali.** Fitur dihitung satu pipeline, dipakai semua model & semua orang tim. Tanpa ini, tiap data scientist ngulang feature engineering yang sama → buang jam kerja (jam engineer itu biaya termahal di ML).
- **Bunuh train/serve skew = bunuh bug mahal.** Skew itu bug diam yang ngirim prediksi salah ke produksi — rekomendasi jelek, churn naik, keputusan bisnis ngaco. Susah di-debug, makan waktu berhari-hari. Di sini hilang by design.
- **Serving murah & cepat.** Redis nyajiin fitur yang udah dihitung dalam milidetik — ga ada recompute mahal tiap request. Latency rendah = UX bagus + biaya compute rendah.
- **Batch terjadwal = biaya predictable.** Refresh harian (APScheduler) jauh lebih murah & stabil dibanding ngitung on-demand terus-terusan.
- **Iterasi lebih cepat.** Satu source of truth + katalog fitur → orang baru langsung paham, eksperimen model lebih ngebut. Time-to-market turun.
- **Infra commodity.** Cukup PostgreSQL + Redis (open source, jalan di Docker lokal) — ga perlu platform feature-store komersial yang mahal.

> **Punchline penutup:** "Feature store ini ngubah feature engineering dari kerja berulang yang rawan bug, jadi **aset** yang dihitung sekali dan dipakai berkali-kali — itu yang bikin tim ML lebih **cepat** sekaligus lebih **murah**."

## A8. Bonus — beda dari project "model deployment" (antisipasi pertanyaan dosen)

Kalau dosen nanya *"bedanya sama project kelas (FastApi_ses7) apa? Kan sama-sama ada ingestion, eval, ML flow, FastAPI?"* — ini jawabannya.

**Inti:** Project kelas itu **MODEL deployment**. Feature store ini **bukan**. Yang satu **ngelatih model & nyajiin prediksi**. Yang satu **ngitung fitur & nyajiin input buat model** — dia ga punya model sama sekali. Beda **layer**, bukan dua hal sama dengan baju beda.

| Surface yang keliatan sama | Di FastApi_ses7 (kelas) | Di feature-store-mvp |
|---|---|---|
| **Ingestion** | `data_ingestion.py` = copy CSV ke folder `ingested/`. 1 fungsi, tanpa validasi. | Ingestion layer: validasi skema + cleaning + normalisasi sebelum fitur dihitung. |
| **Evaluation** | Evaluasi **MODEL**: accuracy / precision / recall. | Evaluasi **DATA**: drift monitoring (Evidently). |
| **"ML flow" / pipeline** | `train_*.py`: fit RandomForest, log MLflow, simpan `model.pkl`. Output = **model**. | Feature pipeline: transform → 23 fitur. **Ga ada model dilatih.** Output = **fitur**. |
| **FastAPI** | `POST /predict`: kirim 18 input mentah → `model.predict()` → balik `burnout_level`. | `GET /features/online/{user_id}`: kirim **ID** → balik **fitur tersimpan** (bukan prediksi). |

**Insight yang nampol:** `MentalHealthFeatures` di app kelas punya 18 field (`age`, `stress_level`, `anxiety_score`, dst.) — itu semua **FITUR**. Di project kelas, pemanggil API **wajib ngitung & ngirim 18 fitur itu sendiri** tiap request. Feature store **ngebalik** itu: fitur udah dihitung & disimpan duluan, pemanggil cukup kirim `user_id`. Jadi:
- **Project kelas = DOWNSTREAM** (konsumen fitur → keluarin prediksi).
- **Feature store = UPSTREAM** (produsen fitur → kasih makan ke model-model).

Mereka **bukan saingan, tapi nyambung**. Model burnout kelas itu justru **contoh sempurna konsumen** feature store — bisa narik 18 fiturnya dari store daripada ngitung ulang tiap request. Dan poin paling tajam: *di project kelas, siapa yang jamin `anxiety_score` dihitung dengan cara yang sama waktu training (dari CSV) dan waktu serving (dari pemanggil)? Ga ada.* Itu **train/serve skew** — persis yang feature store ini selesaiin.

> **Versi siap-ucap:** "Pak, ini beda layer. Yang di kelas itu *model deployment* — ngelatih satu model, evaluasinya accuracy/precision/recall, API-nya `/predict` ngeluarin prediksi. Yang ini *feature store* — ga ngelatih model, dia ngitung fitur & nyajiinnya lewat dua store (Postgres buat training, Redis buat real-time), evaluasinya bukan akurasi tapi drift data. Feature store itu **di atas** (upstream) model deployment — bahkan model burnout di kelas bisa jadi konsumennya, tinggal kirim `student_id` daripada ngitung 18 fitur tiap request. Intinya: feature store nyelesaiin **train/serve skew**, masalah yang justru kebuka di pipeline model deployment biasa."

---

# BAGIAN B — Pitch untuk Customer (untuk pengguna bisnis non-teknis)

> **Catatan cara pakai bagian ini:** Customer kebanyakan **ga ngerti** istilah "feature", "skew", "inference". Jadi di bagian ini SEMUA dijelasin pakai bahasa sehari-hari + contoh nyata + duit. Hindari jargon. Kalau kepaksa pakai istilah teknis, langsung kasih analoginya.

## B0. Elevator pitch (1 kalimat)

> **"Ini sistem yang otomatis bikin 'profil pintar' tiap pelangganmu — dihitung sekali tiap hari, bisa ditanya kapan aja cuma pakai ID pelanggan, jawabannya keluar dalam sekejap. Hasilnya: rekomendasi, promo, dan layananmu jadi lebih tepat sasaran, lebih cepat, dan lebih murah."**

## B1. Siapa target customer-nya?

Produk ini **B2B** (dijual ke bisnis, bukan ke orang per orang). Dua lapis "customer":

**🎯 Yang ngambil keputusan beli (non-teknis) — ini yang kita pitch:**
- **Pemilik / Founder bisnis e-commerce** (toko online, marketplace, brand D2C).
- **Head of Data / Head of Analytics** — yang pusing ngurus data pelanggan.
- **CTO / VP Engineering** — yang mikirin efisiensi tim & biaya infra.
- **Product / Growth Manager** — yang ngurus retensi, personalisasi, & promo.

**🛠️ Yang make sehari-hari (teknis) — di dalam tim customer:**
- **Data Scientist & ML Engineer** mereka. Tapi mereka **pengguna**, bukan pengambil keputusan beli.

**Profil bisnis paling pas (sweet spot):**
- Toko online / marketplace yang **udah punya data transaksi pelanggan** (ribuan+ pelanggan).
- **Udah atau mau pakai "fitur pintar"**: rekomendasi produk, cegah pelanggan kabur (churn), segmentasi pelanggan, deteksi penipuan, promo personal.
- **Startup / scale-up** yang udah punya 2–3 sistem pintar dan mulai **kewalahan ngurus data pelanggan yang berulang-ulang**.

## B2. Analogi yang bikin customer langsung paham: "Dapur Pusat" 🍳

> Jaringan restoran besar **ga masak bahan dasar di tiap cabang**. Mereka punya **dapur pusat** yang nyiapin bahan (saus, adonan, potongan) **sekali**, dengan resep & standar yang **sama**, lalu kirim ke semua cabang. Hasilnya: **rasa konsisten** di semua cabang, **lebih murah** (beli grosir, ga ada kerja dobel), **lebih cepat saji**.
>
> **Feature store = dapur pusat buat data pelanggan.** "Bahan" (profil & sinyal pelanggan) disiapin **sekali**, dipakai semua "cabang" (sistem rekomendasi, promo, deteksi churn, dll). Tanpa dapur pusat, tiap cabang masak sendiri-sendiri → rasanya beda-beda, boros, lambat.

Itu aja udah cukup buat customer ngerti **kenapa** mereka butuh ini.

## B3. Cara pakainya (sehari-hari, 4 langkah)

| Langkah | Apa yang terjadi | Siapa yang ngerjain |
|---|---|---|
| **1. Sekali sambung** | Tim data customer nyambungin data transaksi mereka (file/database) ke sistem ini. Setup sekali di awal. | Tim data customer (dibantu kita) |
| **2. Otomatis tiap hari** | Sistem ngitung **23 sinyal pelanggan** buat tiap pelanggan, **tiap hari, sendiri**. Ga perlu diurus manual. | Sistem (otomatis) |
| **3. Tinggal "tanya"** | Aplikasi / web / sistem promo mereka **kirim ID pelanggan**, sistem balikin **profil lengkapnya dalam sekejap** (hitungan milidetik). | Aplikasi mereka (otomatis) |
| **4. Pantau** | Dashboard nunjukin data masih **sehat & fresh**. Kalau ada yang aneh, ketauan. | Tim data customer |

**Inti cara pakai buat customer:** *"Kamu ga perlu ngitung apa-apa pas pelanggan lagi belanja. Tanya pakai ID, profil pelanggannya langsung muncul. Persis kayak nanya saldo lewat ATM — tinggal colok kartu, saldo langsung keluar, ga dihitung dari nol tiap kali."*

## B4. Skenario penggunaan nyata (bikin customer ngebayangin)

**🛒 Skenario 1 — Cegah pelanggan kabur (churn).**
Sistem liat Pelanggan A udah **60 hari ga belanja** dan **ga aktif sebulan**. → Otomatis trigger kirim kupon "kangen kamu nih, diskon 20%". → *Tanpa sistem ini: ga ada yang sadar Pelanggan A mau kabur sampai keburu telat.*

**🎁 Skenario 2 — Rekomendasi yang pas.**
Pelanggan buka app → sistem tanya "user ini sukanya apa?" → dapet *"sering beli elektronik, suka eksplor banyak kategori"* → tampilin gadget baru yang relevan. **Dalam milidetik**, jadi app ga lemot. → *Rekomendasi tepat = lebih banyak yang beli.*

**👑 Skenario 3 — Layani pelanggan VIP beda.**
Customer service buka tiket → langsung keliatan pelanggan ini **total belanja Rp 50 juta** (top spender). → Prioritasin & kasih layanan ekstra. → *Pelanggan berharga ga ke-cuekin.*

**💸 Skenario 4 — Promo tepat sasaran (ga buang margin).**
Sistem tau siapa **pemburu diskon** (selalu nunggu promo) vs siapa yang **ga sensitif harga**. → Kasih promo **cuma** ke yang butuh dorongan. → *Ga ngasih diskon ke orang yang sebenernya tetep beli full price = hemat margin.*

## B5. Kenapa menguntungkan buat customer (real-world + duit)

| | **Tanpa feature store (sekarang)** | **Dengan feature store** | **Untungnya** |
|---|---|---|---|
| **Kerja tim data** | Tiap bikin sistem pintar baru, ngitung ulang "siapa pelanggan ini" dari nol | Dihitung sekali, dipakai semua | **Hemat gaji-jam** karyawan termahal; sistem baru lebih cepat jadi |
| **Akurasi keputusan** | Angka diam-diam meleset → rekomendasi/promo ngaco tanpa ketauan | Angka konsisten, by design | **Cegah kebocoran revenue** yang ga keliatan |
| **Kecepatan** | Halaman/app loading lama pas ngitung data | Jawaban dalam milidetik | **Lebih banyak yang jadi beli** (orang ga kabur karena lemot) |
| **Biaya infra** | (Kalau beli platform komersial) bisa puluhan ribu dolar/tahun | Cukup software open-source di server sendiri | **Kemampuan kelas enterprise, tanpa harga enterprise** |
| **Nambah fitur baru** | Bangun ulang data dari nol tiap use-case | Tinggal "tanya" data yang udah ada | **Inovasi lebih ngebut**, time-to-market turun |

**3 kalimat yang paling ngena buat customer:**
1. **"Tim mahalmu berhenti ngerjain hal yang sama berulang."** Data scientist itu salah satu karyawan termahal — sistem ini bikin mereka ga buang waktu ngitung ulang.
2. **"Berhenti ambil keputusan dari angka yang diam-diam salah."** Ini bug yang ga bikin error/crash — sistemmu kelihatan jalan normal tapi pelan-pelan jadi ngaco, dan kamu baru sadar pas **revenue turun**. Sistem ini ngilangin itu.
3. **"Pengalaman pelanggan jadi cepat & personal — dua hal yang langsung naikin penjualan."**

## B6. FAQ singkat (buat handle keberatan customer)

**"Kan saya udah punya database, ngapain ini lagi?"**
Database nyimpen **data mentah** (catatan transaksi). Ini nyimpen **sinyal yang udah diolah & siap pakai** + jamin angkanya konsisten + jawab dalam milidetik. Beda fungsi — kayak beda antara *gudang bahan* dan *dapur pusat*.

**"Butuh tim besar & mahal buat jalanin?"**
Engga. Infrastrukturnya **ringan** — cuma 2 komponen software gratis (PostgreSQL + Redis) yang jalan di server biasa.

**"Data pelanggan saya aman?"**
Ya — sistem ini jalan di **infrastruktur kamu sendiri** (server/komputer kamu), bukan ngirim data ke pihak ketiga.

**"Berapa cepat keliatan hasilnya?"**
Setelah disambung ke data, sistem langsung ngitung profil pelanggan tiap hari. Sistem pintar (rekomendasi/promo) yang nyambung ke sini bisa langsung nikmatin data yang konsisten & cepat.

## B7. Ringkasan 1 slide (kalau cuma boleh 1 halaman)

> **Feature Store** = "dapur pusat" buat data pelangganmu.
>
> - **Apa:** Otomatis bikin profil pintar (23 sinyal) tiap pelanggan, tiap hari.
> - **Cara pakai:** Sambung sekali → tinggal tanya pakai ID pelanggan → profil keluar dalam milidetik.
> - **Buat siapa:** Bisnis e-commerce yang pakai rekomendasi / promo / cegah churn dan mau lebih efisien.
> - **Kenapa untung:** (1) hemat waktu tim mahal, (2) cegah keputusan dari angka salah, (3) pengalaman pelanggan cepat = penjualan naik, (4) biaya infra kecil.
>
> **"Dihitung sekali, dipakai berkali-kali — bikin bisnis lebih cepat sekaligus lebih murah."**
