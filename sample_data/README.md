# DEM untuk Pemodelan Genangan

Letakkan **DEM GeoTIFF** di folder ini agar mesin genangan memakai data
elevasi nyata (bukan DEM sintetis demo).

## Konvensi nama file
- `<pos_id>.tif` → DEM khusus untuk satu pos (mis. `2.tif` untuk pos Jurug).
- `dem.tif` → DEM umum yang dipakai bila DEM per-pos tidak ada.

## Cara mendapatkan DEM Indonesia
1. **DEMNAS** (resolusi ~8 m) — portal **BIG**: https://tanahair.indonesia.go.id/demnas/
2. **IFSAR / DSM** untuk wilayah tertentu (BIG).
3. Crop DEM ke area sekitar pos (mis. radius ~3 km) lalu simpan sebagai GeoTIFF.

```bash
# contoh crop dengan GDAL (bbox: xmin ymin xmax ymax dalam derajat)
gdalwarp -te 110.836 -7.592 110.886 -7.542 demnas_full.tif sample_data/2.tif
```

## Catatan datum penting
Ambang siaga & `elevasi_cm` BBWS berbasis **peilschaal/datum lokal pos**.
Pastikan DEM berada pada **datum vertikal yang sama** (atau lakukan koreksi
offset) agar perbandingan elevasi tanah vs muka air benar.

> GeoTIFF di folder ini **tidak ikut di-commit** (lihat `.gitignore`) karena
> ukurannya besar.
