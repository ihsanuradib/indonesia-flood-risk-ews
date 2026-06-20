# 🌊 Indonesia Flood Risk EWS — WebGIS Early Warning System

WebGIS **Early Warning System** dan **Flood Inundation Mapper** untuk Daerah Aliran Sungai (DAS) **Bengawan Solo**, terinspirasi oleh [USGS Flood Inundation Mapper](https://fim.wim.usgs.gov/fim/) namun dikembangkan untuk konteks Indonesia menggunakan **Python**.

Aplikasi menampilkan **tinggi muka air (TMA)**, **debit**, dan **curah hujan** secara mendekati real-time dari jaringan pos hidrologi **BBWS Bengawan Solo**, mengklasifikasikan status siaga (hijau/kuning/merah), serta memodelkan **genangan banjir** untuk setiap pos duga air.

> **Live demo (GitHub Pages):** `https://ihsanuradib.github.io/indonesia-flood-risk-ews/`

---

## ✨ Fitur

- **Peta interaktif (Leaflet)** dengan basemap jalan, citra satelit, dan topografi.
- **Marker pos** berwarna sesuai status siaga; popup berisi grafik muka air vs ambang siaga (Chart.js).
- **Dashboard**: jumlah pos, jumlah pos siaga, daftar peringatan aktif, filter tipe/wilayah.
- **Model Genangan Banjir** dengan _slider_ muka air — menghitung luas & sebaran genangan secara interaktif.
- **Dua mode operasi** (lihat Arsitektur).

## 🏗️ Arsitektur

Karena **GitHub Pages hanya melayani file statis**, proyek ini dirancang agar tetap bisa dikembangkan dengan Python namun tampil di GitHub Pages:

```
┌─────────────────────────┐      ┌──────────────────────────────┐
│  Frontend (Leaflet)     │      │  Backend (Python / FastAPI)  │
│  docs/  → GitHub Pages   │◀────▶│  backend/  → Render/Railway   │
│  - peta, dashboard       │ API  │  - normalisasi data BBWS      │
│  - mode statis (snapshot)│      │  - model genangan (DEM/HAND)  │
└──────────┬──────────────┘      └──────────────┬───────────────┘
           │                                    │
           │   GitHub Actions (cron 15 mnt)     │
           ▼                                    ▼
   docs/data/stations.geojson  ◀──  data_pipeline/build_static.py  ──▶  API BBWS
```

**Mode A — GitHub Pages saja (tanpa server):** `data_pipeline/build_static.py` (dijalankan otomatis oleh GitHub Actions tiap 15 menit) mengambil data BBWS dan menyimpannya sebagai `docs/data/stations.geojson`.

**Mode B — Backend Python live:** deploy `backend/` (FastAPI) ke Render/Railway, lalu isi `API_BASE` di `docs/js/config.js`.

## 🌊 Pemodelan Genangan Banjir

Mesin genangan (`backend/app/services/inundation.py`) memakai metode **HAND / bathtub (planar water-surface)** — pendekatan yang sama dengan _rapid_ Flood Inundation Mapping NOAA/USGS

## 🚀 Menjalankan Lokal

**Backend (FastAPI):**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
# Dokumentasi API: http://127.0.0.1:8000/docs
```

**Frontend:**

```bash
cd docs
python -m http.server 5500   # buka http://127.0.0.1:5500
```

Untuk memakai backend lokal, set `API_BASE: "http://127.0.0.1:8000"` di `docs/js/config.js`.

## 📡 Endpoint API

| Method | Endpoint                 | Keterangan                                                |
| ------ | ------------------------ | --------------------------------------------------------- |
| GET    | `/api/stations`          | GeoJSON semua pos (filter `tipe`, `wilayah`, `min_siaga`) |
| GET    | `/api/stations/summary`  | Ringkasan & daftar peringatan                             |
| GET    | `/api/stations/{pos_id}` | Detail satu pos                                           |
| POST   | `/api/inundation`        | Model genangan untuk satu pos TMA                         |

## 🌐 Deploy

**GitHub Pages:** Settings → Pages → Source: `master` / folder `/docs`.
**Backend:** push ke GitHub lalu buat _Blueprint_ di [Render](https://render.com) (file `render.yaml` sudah disertakan).

## 📂 Struktur

```
indonesia-flood-risk-ews/
├── backend/            # FastAPI: data + model genangan
│   └── app/
│       ├── routers/    # stations, inundation
│       └── services/   # bbws_client, siaga, inundation
├── docs/               # Frontend statis (GitHub Pages)
│   ├── index.html
│   ├── css/ js/ data/
├── data_pipeline/      # build_static.py (snapshot GeoJSON)
├── sample_data/        # taruh DEM GeoTIFF di sini
├── .github/workflows/  # auto-refresh data (cron)
└── render.yaml         # deploy backend
```

## 🙋 Sumber Data

Data hidrologi: **BBWS Bengawan Solo** — https://hidrologi.bbws-bsolo.net

## 👤 Penulis

**M Ihsanur Adib**

## 📄 Lisensi

MIT
