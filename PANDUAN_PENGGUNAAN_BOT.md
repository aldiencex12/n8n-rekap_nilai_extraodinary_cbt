# 📖 BUKU PANDUAN LENGKAP PENGGUNAAN BOT REKAP NILAI CBT
**SMP Hang Tuah 5 Sidoarjo**  
*Platform: Extraordinary CBT ➔ n8n Automation Engine ➔ Telegram Bot (@rekapnilaismpht5_bot)*

---

## 📌 I. Prinsip Kerja Sistem
1. **Otomatis Aktif**: Bot berjalan sebagai layanan sistem background (`systemd service`) pada laptop proktor. Setiap kali laptop menyala dan terhubung ke internet, bot langsung aktif tanpa perlu membuka terminal.
2. **Keamanan Database CBT**: Database CBT adalah sumber kebenaran data (*single source of truth*). Semua jawaban siswa, log login, dan nilai tersimpan permanen di server CBT. Bot hanya bertugas membaca data, memicu perhitungan nilai, dan mencetaknya ke format PDF resmi.
3. **Fleksibel (Tombol & Teks)**: Semua aksi dapat dilakukan lewat tombol interaktif (*inline keyboard*) maupun perintah teks langsung.

---

## 🗺️ II. Alur Operasional Harian

```text
               [ 1. UJIAN BERJALAN ]
                        │
                        ▼
         Pantau status & sisa waktu siswa
         👉 Perintah: /monitor atau tombol '⏳ Monitor Ujian (Live)'
                        │
                        │
               [ 2. WAKTU UJIAN SELESAI ]
                        │
                        ▼
         Kunci & submit otomatis siswa yang belum submit
         👉 Perintah: /forcefinish atau tombol '⚡ Force Finish Semua'
                        │
                        │
               [ 3. TARIK & HITUNG NILAI ]
                        │
                        ▼
         Tarik nilai dari server CBT & susun ke format rekap
         👉 Perintah: /rekap atau tombol '🔄 Tarik Data Baru CBT'
                        │
                        ├──────────────────────────┐
                        │                          │
                        ▼                          ▼
             [ 4. UNDUH PDF NILAI ]       [ 5. REKAP SUSULAN ]
                        │                          │
         Unduh per kelas / ZIP semua       Cetak daftar siswa absen
         👉 Ketik: 8D atau /pdf all        👉 Perintah: /susulan
                        │                          │
                        └─────────────┬────────────┘
                                      │
                                      ▼
                        [ 6. PERSIAPAN HARI BERIKUTNYA ]
                        Bersihkan file PDF lokal laptop
                        👉 Perintah: /reset
```

---

## 📑 III. Panduan Perintah & Fitur

### 1. Menu Utama
* **Perintah:** `/start` atau `/menu`
* **Fungsi:** Memunculkan kembali dasbor tombol navigasi utama.

### 2. Monitoring Ujian Real-Time (`/monitor`)
* **Perintah:** `/monitor`, `/pantau`, `/status`, atau tombol **`⏳ Monitor Ujian (Live)`**
* **Fungsi:** Mengetahui kondisi peserta saat sesi ujian berlangsung:
  - 🟢 **Sudah Selesai:** Siswa yang sudah submit (nilai aman).
  - 🟡 **Sedang Mengerjakan:** Siswa yang masih aktif di soal beserta sisa waktu pengerjaan.
  - 🔵 **Persiapan:** Siswa yang baru login di halaman token.

### 3. Force Finish / Submit Otomatis (`/forcefinish`)
* **Perintah:** `/forcefinish`, `forcefinish`, atau tombol **`⚡ Force Finish Semua`**
* **Fungsi:** Mengunci dan men-submit otomatis seluruh siswa yang masih berstatus *Sedang Mengerjakan* (karena lupa klik selesai atau komputer mati), sehingga nilainya langsung terhitung di CBT.
* **Per Siswa:** `/forcefinish [NOMOR_UJIAN]` (contoh: `/forcefinish 26-001-015`).

### 4. Tarik Nilai & Generate Rekap (`/rekap`)
* **Hari Ini:** Ketik `/rekap` atau sentuh tombol **`🔄 Tarik Data Baru CBT`**.
* **Tanggal Lalu:** Ketik `/rekap YYYY-MM-DD` (contoh: `/rekap 2026-09-07`).
* **Kelas Tertentu:** Ketik `/rekap [KELAS]` (contoh: `/rekap 8D`).

### 5. Mengunduh Dokumen Nilai PDF
* **Per Kelas:** Cukup kirim nama kelas (contoh: `8D`, `7A`, `9C`) atau tekan tombol kelas di menu.
* **Semua Kelas Sekaligus:** Sentuh tombol **`📦 Unduh Semua PDF (ZIP)`** atau ketik `/pdf all`.

### 6. Rekap Ujian Susulan (`/susulan`)
* **Perintah:** `/susulan` atau tombol **`📋 Rekap Susulan`**
* **Fungsi:** Mencetak dokumen resmi **Daftar Siswa Ujian Susulan** berisi daftar siswa yang absen/belum ujian beserta kolom tanda tangan pengawas ruangan.

### 7. Membersihkan File PDF Laptop (`/reset`)
* **Perintah:** `/reset`, `/clean`, `/hapus`, atau tombol **`🧹 Bersihkan File PDF Lama`**
* **Fungsi:** Menghapus file cetak PDF di laptop. Nilai di CBT tetap aman 100%.

---

## 📂 IV. Aturan Penumpukan File Antar-Tanggal (Multi-Date)

Format file PDF di laptop dinamai berdasarkan: `Nilai_[KELAS]_[MATA_PELAJARAN].pdf`.

### Skenario Penarikan 2 Tanggal Berbeda:
Jika Anda menjalankan `/rekap 2026-09-07` (Hari 1: IPA & PJOK), lalu menjalankan `/rekap 2026-09-08` (Hari 2: B.Inggris & Informatika):
* **Jika TIDAK menekan `/reset`:**
  Saat Anda klik **8D**, bot akan mengirimkan **keempat file PDF tersebut sekaligus** (IPA, PJOK, B.Inggris, Informatika).
  > **Cocok untuk:** Mengumpulkan bundel arsip nilai seluruh mapel yang sudah selesai diujikan.
* **Jika menekan `/reset` di awal hari:**
  File hari sebelumnya terhapus dari laptop, sehingga saat Anda klik **8D**, bot hanya mengirimkan **file ujian hari itu saja**.
  > **Cocok untuk:** Laporan harian per mapel agar tidak tercampur dengan hari kemarin.

---

## 🛠️ V. Berbagai Skenario Lapangan & Solusinya

### Skenario 1: Siswa Pulang / Keluar Ruangan Tanpa Menekan Tombol "Selesai"
* **Masalah:** Nilai siswa tidak muncul di rekap (kosong / strip), padahal siswa hadir dan menjawab soal.
* **Penyebab:** Status ujian di CBT masih `Sedang Dikerjakan` (status 1).
* **Solusi:**
  1. Buka bot Telegram, ketik `/monitor` untuk memeriksa daftar siswa yang tertahan.
  2. Sentuh tombol **`⚡ Force Finish Semua`** (atau ketik `/forcefinish`).
  3. Setelah bot mengonfirmasi berhasil, ketik `/rekap`.
  4. Unduh kembali PDF kelas tersebut. Nilai siswa sudah keluar lengkap.

---

### Skenario 2: Siswa Sakit/Izin Mengikuti Ujian Susulan di Hari Berikutnya
* **Masalah:** Siswa kemarin absen (ditandai merah "Tidak Hadir" di rekap kemarin), hari ini telah selesai mengerjakan ujian susulan di CBT. Bagaimana cara memperbarui rekap nilainya?
* **Solusi:**
  1. Pastikan ujian susulan siswa di CBT sudah berstatus Selesai (bisa dicek dengan `/monitor` atau di-forcefinish jika waktu habis).
  2. Buka bot, ketik perintah `/rekap` diikuti tanggal ujian asli siswa tersebut:
     ```text
     /rekap 2026-09-07
     ```
  3. n8n akan menyedot ulang data CBT tanggal tersebut. Nilai siswa susulan otomatis terisi menggantikan tanda strip merah, dan statusnya berubah menjadi **Hadir**.
  4. Unduh kembali PDF kelas siswa tersebut.

---

### Skenario 3: Guru Pengampu Meminta Kembali Rekap Kemarin, Padahal File PDF di Laptop Sudah Dibersihkan (`/reset`)
* **Masalah:** Admin kemarin sudah menekan `/reset` sehingga folder PDF di laptop kosong. Guru meminta salinan nilai kemarin.
* **Solusi:**
  - Jangan khawatir! Database server CBT tidak pernah terhapus.
  - Cukup ketik:
    ```text
    /rekap 2026-09-07
    ```
  - Bot akan mengambil kembali data kemarin dari server CBT dan mencetak ulang PDF-nya dalam hitungan detik.

---

### Skenario 4: Laptop Proktor Mati Lampu / Restart Mendadak Saat Ujian Berlangsung
* **Masalah:** Laptop mati di tengah ujian. Apakah bot harus disetel ulang dari terminal?
* **Solusi:**
  - **TIDAK PERLU.** Bot sudah didaftarkan sebagai *systemd service background*.
  - Begitu laptop dinyalakan kembali dan terhubung ke Wi-Fi / LAN sekolah, bot langsung otomatis menyala sendiri di latar belakang dan siap menerima perintah.

---

### Skenario 5: Butuh Mencetak Seluruh Kelas (7A s/d 9E) untuk Arsip Kurikulum
* **Masalah:** Terlalu lama jika harus mengunduh file kelas satu per satu (ada 15 kelas).
* **Solusi:**
  - Sentuh tombol **`📦 Unduh Semua PDF (ZIP)`** atau ketik `/pdf all`.
  - Bot akan mengompres seluruh file PDF semua jenjang kelas ke dalam satu file arsip ZIP (`Rekap_Nilai_CBT_Semua_Kelas.zip`) yang langsung bisa Anda ekstrak di komputer kantor.

---

### Skenario 6: Butuh Lembar Presensi Khusus untuk Ruang Ujian Susulan
* **Masalah:** Pengawas ruang susulan membutuhkan berkas daftar peserta yang berhak mengikuti susulan beserta kolom paraf hadir.
* **Solusi:**
  - Ketik `/susulan` atau sentuh **`📋 Rekap Susulan`**.
  - Dokumen PDF resmi siap cetak lengkap dengan nama, nomor peserta, mata pelajaran, dan kolom tanda tangan pengawas ruangan akan langsung dikirim oleh bot.

---

## ⚡ Ringkasan Perintah Cepat

| Perintah | Fungsi Utama |
| :--- | :--- |
| `/start` | Membuka tombol menu interaktif |
| `/monitor` | Cek status ujian peserta secara live |
| `/forcefinish` | Kunci & submit otomatis siswa yang tertahan |
| `/rekap` | Tarik nilai ujian hari ini dari CBT |
| `/rekap YYYY-MM-DD` | Tarik nilai ujian tanggal tertentu |
| `8D` *(atau kelas lain)* | Unduh PDF nilai kelas tersebut |
| `/pdf all` | Unduh semua kelas dalam bentuk ZIP |
| `/susulan` | Cetak berkas resmi daftar siswa susulan |
| `/reset` | Bersihkan file PDF lokal laptop |
