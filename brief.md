
Namun, **detail workflow n8n yang mengambil/merekap nilai dari Extraordinary belum tersimpan dengan cukup jelas** di hasil yang saya temukan. Jadi saya tidak mau mengarang seolah-olah masih ingat node persisnya.

### Yang saya pahami tentang project itu

Konsepnya kira-kira seperti ini:

```text
                    EXTRAORDINARY
                         │
                         ▼
                  Data nilai siswa
                         │
                         ▼
                    ┌─────────┐
                    │   n8n   │
                    └────┬────┘
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
        Ambil data siswa       Ambil data nilai
              │                     │
              └──────────┬──────────┘
                         ▼
                  Cocokkan siswa
                         │
                         ▼
                  Bersihkan data
                         │
                         ▼
                 Hitung / rekap
                         │
                         ▼
                Simpan hasil rekap
                         │
             ┌───────────┼───────────┐
             ▼           ▼           ▼
          Database     Excel       GuruHub
```

Yang menarik dari project tersebut adalah **n8n bukan sekadar mengambil data**, tetapi menjadi semacam **jembatan/mesin sinkronisasi** antara data nilai dari Extraordinary dengan sistem rekap yang kamu gunakan.

### Bagian yang paling penting

Misalnya Extraordinary menghasilkan data seperti:

```text
Nama                 Mapel       Nilai
ADELARD DAMA         Informatika  85
AHMAD ARYA           Informatika  90
BUDI                 Informatika  78
```

n8n kemudian perlu melakukan beberapa tahap.

**1. Trigger**

Workflow dimulai, misalnya:

```text
Manual Trigger
      ↓
HTTP Request
```

atau dijalankan otomatis:

```text
Schedule Trigger
      ↓
Ambil data Extraordinary
```

**2. Mengambil data**

Node HTTP Request mengambil data dari Extraordinary.

Hasil mentahnya mungkin berupa:

```json
{
  "student": "ADELARD DAMA",
  "subject": "Informatika",
  "score": 85
}
```

Tetapi data nyata biasanya tidak sesederhana itu. Bisa saja ada ID siswa, kelas, semester, jenis ujian, tanggal, dan sebagainya.

**3. Normalisasi**

Ini bagian yang sangat penting.

Contohnya:

```text
"ADELARD DAMA SYAHPUTRA"
```

harus bisa dicocokkan dengan data siswa di sistem kita.

n8n bisa membersihkan:

* spasi ganda
* huruf besar/kecil
* karakter aneh
* nama yang berbeda format
* nilai dalam bentuk string
* ID siswa
* kelas
* mata pelajaran

Contohnya:

```javascript
{
  nama: "ADELARD DAMA SYAHPUTRA",
  kelas: "VIII A",
  mapel: "INFORMATIKA",
  nilai: 85
}
```

**4. Pencocokan siswa**

Ini justru salah satu bagian paling krusial.

Jangan hanya mengandalkan nama.

Lebih aman:

```text
ID Siswa
   ↓
cocokkan
   ↓
ID Siswa di database
```

Kalau Extraordinary punya ID siswa yang sama dengan database GuruHub, masalah pencocokan menjadi jauh lebih mudah.

Kalau tidak ada ID yang sama, baru menggunakan kombinasi:

```text
Nama + Kelas
```

atau bahkan:

```text
Nama + Kelas + NIS
```

**5. Pengelompokan nilai**

Setelah semua data cocok, n8n dapat mengelompokkan:

```text
Siswa
 ├── Informatika
 │    ├── Sumatif 1
 │    ├── Sumatif 2
 │    ├── STS
 │    └── SAS
 │
 ├── Matematika
 │    ├── Sumatif 1
 │    └── STS
 │
 └── Bahasa Indonesia
      ├── Sumatif 1
      └── STS
```

Kemudian baru dihitung sesuai aturan yang kamu tentukan.

Misalnya:

```text
Sumatif 1 = 80
Sumatif 2 = 90
STS       = 85

Rata-rata = (80 + 90 + 85) / 3
          = 85
```

Hal ini sejalan dengan rancangan sistem GuruHub yang memang memiliki **grade engine** untuk menghitung nilai akhir siswa.

---

### 6. Hasil akhirnya

Saya membayangkan tujuan workflow kamu bukan sekadar:

```text
Extraordinary → n8n → Excel
```

tetapi lebih seperti:

```text
                    ┌──────────────┐
                    │ Extraordinary│
                    └──────┬───────┘
                           │
                           ▼
                    ┌─────────────┐
                    │     n8n     │
                    │             │
                    │ 1. Fetch    │
                    │ 2. Clean    │
                    │ 3. Match    │
                    │ 4. Group    │
                    │ 5. Calculate│
                    │ 6. Validate │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ Rekap Nilai │
                    └──────┬──────┘
                           │
                 ┌─────────┼─────────┐
                 ▼         ▼         ▼
              Database   Excel    GuruHub
```

Dan nantinya data tersebut bisa dipakai untuk **leger nilai dan rapor**, karena rancangan GuruHub memang menyediakan ekspor leger Excel dan rapor akademik.

### Tapi saya ingin memastikan satu hal

Kalau kamu ingin saya **membongkar kembali project n8n kita secara detail sampai node per node**, paling bagus kamu kirim **workflow n8n yang sekarang** (`.json`) atau screenshot workflow-nya.

Kalau kamu kirim JSON workflow n8n-nya, saya bisa jelaskan **setiap node, aliran datanya, fungsi masing-masing Code node, struktur JSON input/output, sampai bagian mana yang mengambil data Extraordinary dan bagaimana rekap nilainya terbentuk**.
