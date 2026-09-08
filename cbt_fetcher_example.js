const puppeteer = require('puppeteer');

// ============================================================================
// CONTOH SCRIPT PENARIKAN DATA NILAI (SCRAPING)
// PERINGATAN: Gunakan URL dan kredensial dummy di bawah ini sebagai contoh.
// Ganti dengan URL dan endpoint API sistem Anda yang sebenarnya saat produksi.
// ============================================================================

const CBT_URL = 'https://cbt.example.com/adm';
const LOGIN_EMAIL = 'admin@example.com';
const LOGIN_PASSWORD = 'your_secure_password';

async function fetchGrades() {
  console.log('Memulai browser...');
  const browser = await puppeteer.launch({ headless: true });
  const page = await browser.newPage();

  try {
    console.log(`Navigasi ke halaman login: ${CBT_URL}`);
    await page.goto(CBT_URL, { waitUntil: 'networkidle2' });

    // 1. Mengisi form login (Sesuaikan selektor CSS dengan struktur HTML web Anda)
    console.log('Mengisi kredensial login...');
    await page.type('input[name="email"]', LOGIN_EMAIL);
    await page.type('input[name="password"]', LOGIN_PASSWORD);

    // 2. Klik tombol login dan tunggu hingga navigasi selesai
    console.log('Menekan tombol login...');
    await Promise.all([
      page.click('button[type="submit"]'),
      page.waitForNavigation({ waitUntil: 'networkidle2' }),
    ]);

    // 3. Navigasi ke halaman rekap nilai (ganti dengan URL yang sesuai)
    const gradesUrl = 'https://cbt.example.com/adm/grades';
    console.log(`Navigasi ke halaman nilai: ${gradesUrl}`);
    await page.goto(gradesUrl, { waitUntil: 'networkidle2' });

    // 4. Mengekstrak data nilai dari tabel
    console.log('Mengekstrak data nilai...');
    const grades = await page.evaluate(() => {
      const rows = Array.from(document.querySelectorAll('table.grades-table tbody tr'));
      return rows.map(row => {
        const columns = row.querySelectorAll('td');
        return {
          nama: columns[0] ? columns[0].innerText.trim() : '',
          mapel: columns[1] ? columns[1].innerText.trim() : '',
          nilai: columns[2] ? columns[2].innerText.trim() : ''
        };
      });
    });

    console.log('Data nilai berhasil diambil:');
    console.log(grades);

    // 5. Di sini Anda dapat menambahkan kode untuk mengirim data ke database
    // atau ke sistem GuruHub melalui API.

  } catch (error) {
    console.error('Terjadi kesalahan saat mengambil nilai:', error);
  } finally {
    console.log('Menutup browser...');
    await browser.close();
  }
}

fetchGrades();
