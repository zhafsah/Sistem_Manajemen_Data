import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime

# ==========================================
# 1. PENGATURAN HALAMAN & KONEKSI GOOGLE SHEETS
# ==========================================
st.set_page_config(
    page_title="PRO-Affiliate Multi-Account Analytics", 
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Desain Banner Header Baru yang Mencolok
st.markdown("""
    <div style="background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%); padding: 25px; border-radius: 12px; margin-bottom: 25px; color: white;">
        <h1 style="margin: 0; font-size: 32px;">🚀 PRO-Affiliate Analytics</h1>
        <p style="margin: 5px 0 0 0; opacity: 0.9; font-size: 16px;"><b>Versi Multi-Akun & Aggregator Cloud</b> — Pantau performa iklan Meta dan banyak akun Shopee secara tersentralisasi.</p>
    </div>
""", unsafe_allow_html=True)

# Tambahan Visual di Area Sidebar
with st.sidebar:
    st.markdown("### 🛠️ Sistem Status")
    st.success("🟢 Terhubung ke Cloud Baru")
    
    st.markdown("### 📊 Fitur Multi-Akun")
    st.info("Mendukung kombinasi hingga 5 file CSV sekaligus (Meta Ads + Multi-Akun Shopee Clicks & Sales).")
    
    st.markdown("---")
    st.caption("PRO-Affiliate Analytics Engine v2.0 • 2026")

# Fungsi Koneksi Google Sheets dengan Secrets
@st.cache_resource
def init_gspread():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        # Mengambil kredensial dari Streamlit Secrets
        creds_dict = eval(st.secrets["google_credentials"]["json_teks"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        
        spreadsheet_id = st.secrets["spreadsheet"]["id"]
        sheet = client.open_by_key(spreadsheet_id)
        return sheet
    except Exception as e:
        st.error(f"⚠️ Gagal tersambung ke Google Sheets: {e}")
        return None

sheet = init_gspread()

# Membuat Tab Otomatis jika sheet baru kosong
if sheet:
    try:
        existing_sheets = [s.title for s in sheet.worksheets()]
        required_sheets = ["Riwayat_Summary", "Riwayat_Tag", "Raw_Sales"]
        for rs in required_sheets:
            if rs not in existing_sheets:
                sheet.add_worksheet(title=rs, rows="1000", cols="20")
    except Exception as e:
        pass

# ==========================================
# 2. FUNGSI MEMBACA DATA DARI GOOGLE SHEETS
# ==========================================
def load_data_from_gsheet(sheet_name):
    if not sheet:
        return pd.DataFrame()
    try:
        wks = sheet.worksheet(sheet_name)
        data = wks.get_all_records()
        if not data:
            return pd.DataFrame()
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()

# Load Data untuk Dashboard Visualisasi
df_summary = load_data_from_gsheet("Riwayat_Summary")

# ==========================================
# 3. FILTER DASHBOARD (PILIHAN DATA)
# ==========================================
st.subheader("🔍 Filter Data")

if not df_summary.empty:
    # Memastikan kolom Tanggal dalam format datetime
    df_summary['Tanggal'] = pd.to_datetime(df_summary['Tanggal'], errors='coerce')
    df_summary = df_summary.dropna(subset=['Tanggal'])
    
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        min_date = df_summary['Tanggal'].min().date()
        max_date = df_summary['Tanggal'].max().date()
        start_date = st.date_input("Tanggal Mulai", min_date)
    with col_f2:
        end_date = st.date_input("Tanggal Selesai", max_date)
        
    # Filter Dataframe berdasarkan tanggal
    df_filtered = df_summary[
        (df_summary['Tanggal'].dt.date >= start_date) & 
        (df_summary['Tanggal'].dt.date <= end_date)
    ]
else:
    st.info("Belum ada data di Google Sheets. Silakan lakukan unggah file di bawah terlebih dahulu.")
    df_filtered = pd.DataFrame()

# ==========================================
# 4. KARTU METRIK PREMIUM (DESAIN MULTI-AKUN)
# ==========================================
st.markdown("<br>", unsafe_allow_html=True)

# Kalkulasi Nilai Metrik
if not df_filtered.empty:
    val_spend = pd.to_numeric(df_filtered['Spend'], errors='coerce').sum()
    val_komisi_iklan = pd.to_numeric(df_filtered['Komisi Iklan'], errors='coerce').sum()
    val_komisi_organik = pd.to_numeric(df_filtered['Komisi Organik'], errors='coerce').sum()
    val_keuntungan_iklan = val_komisi_iklan - val_spend
    val_total_keuntungan = pd.to_numeric(df_filtered['Profit'], errors='coerce').sum()
else:
    val_spend = 0
    val_komisi_iklan = 0
    val_komisi_organik = 0
    val_keuntungan_iklan = 0
    val_total_keuntungan = 0

# Format Angka Ribuan ke Gaya Indonesia (Menggunakan titik sebagai ribuan)
str_spend = f"Rp {int(round(val_spend)):,}".replace(',', '.')
str_komisi_iklan = f"Rp {int(round(val_komisi_iklan)):,}".replace(',', '.')
str_komisi_organik = f"Rp {int(round(val_komisi_organik)):,}".replace(',', '.')
str_keuntungan_iklan = f"Rp {int(round(val_keuntungan_iklan)):,}".replace(',', '.')
str_total_keuntungan = f"Rp {int(round(val_total_keuntungan)):,}".replace(',', '.')

# Pembuatan Grid Visual HTML Kartu Metrik
cm1, cm2, cm3, cm4, cm5 = st.columns(5)

with cm1:
    st.markdown(f"""
        <div style="background-color: #FEF2F2; border-left: 5px solid #EF4444; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <p style="margin:0; font-size:12px; color:#991B1B; font-weight:bold; text-transform:uppercase;">💸 Total Ads Spend</p>
            <h3 style="margin:5px 0 0 0; color:#DC2626; font-size:18px; font-weight:bold;">{str_spend}</h3>
        </div>
    """, unsafe_allow_html=True)

with cm2:
    st.markdown(f"""
        <div style="background-color: #EFF6FF; border-left: 5px solid #3B82F6; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <p style="margin:0; font-size:12px; color:#1E40AF; font-weight:bold; text-transform:uppercase;">🎯 Komisi Iklan</p>
            <h3 style="margin:5px 0 0 0; color:#2563EB; font-size:18px; font-weight:bold;">{str_komisi_iklan}</h3>
        </div>
    """, unsafe_allow_html=True)

with cm3:
    st.markdown(f"""
        <div style="background-color: #F5F3FF; border-left: 5px solid #8B5CF6; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <p style="margin:0; font-size:12px; color:#5B21B6; font-weight:bold; text-transform:uppercase;">📱 Komisi Organik</p>
            <h3 style="margin:5px 0 0 0; color:#7C3AED; font-size:18px; font-weight:bold;">{str_komisi_organik}</h3>
        </div>
    """, unsafe_allow_html=True)

with cm4:
    bg_iklan = "#ECFDF5" if val_keuntungan_iklan >= 0 else "#FFF5F5"
    border_iklan = "#10B981" if val_keuntungan_iklan >= 0 else "#EF4444"
    teks_iklan = "#065F46" if val_keuntungan_iklan >= 0 else "#991B1B"
    st.markdown(f"""
        <div style="background-color: {bg_iklan}; border-left: 5px solid {border_iklan}; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <p style="margin:0; font-size:12px; color:{teks_iklan}; font-weight:bold; text-transform:uppercase;">📊 Profit Iklan Murni</p>
            <h3 style="margin:5px 0 0 0; color:{border_iklan}; font-size:18px; font-weight:bold;">{str_keuntungan_iklan}</h3>
        </div>
    """, unsafe_allow_html=True)

with cm5:
    bg_net = "#F0FDF4" if val_total_keuntungan >= 0 else "#FFF5F5"
    border_net = "#22C55E" if val_total_keuntungan >= 0 else "#EF4444"
    teks_net = "#166534" if val_total_keuntungan >= 0 else "#991B1B"
    st.markdown(f"""
        <div style="background-color: {bg_net}; border-left: 5px solid {border_net}; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <p style="margin:0; font-size:12px; color:{teks_net}; font-weight:bold; text-transform:uppercase;">💎 Net Profit (Total)</p>
            <h3 style="margin:5px 0 0 0; color:{border_net}; font-size:18px; font-weight:bold;">{str_total_keuntungan}</h3>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<br><hr>", unsafe_allow_html=True)

# ==========================================
# 5. HALAMAN DATA TABEL (JIKA DATA ADA)
# ==========================================
if not df_filtered.empty:
    st.subheader("📋 Tabel Data Summary Terfilter")
    # Tampilkan salinan tabel terformat tanggal ringkas
    df_display = df_filtered.copy()
    df_display['Tanggal'] = df_display['Tanggal'].dt.strftime('%Y-%m-%d')
    st.dataframe(df_display, use_container_width=True)

# ==========================================
# 6. AREA UNGGUH CSV & PROSES DATA
# ==========================================
st.subheader("📤 Unggah File Laporan Baru")
uploaded_files = st.file_uploader("Pilih file CSV Iklan / Shopee Anda (Bisa lebih dari satu)", type="csv", accept_multiple_files=True)

if uploaded_files:
    st.info(f"📂 Berhasil memuat {len(uploaded_files)} file. Siap diproses ke Google Sheets baru Anda.")
    # Tombol eksekusi proses data bisa Anda tambahkan di bawah ini sesuai logika ekstraksi Anda sebelumnya
