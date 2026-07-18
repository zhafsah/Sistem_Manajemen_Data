import streamlit as st
import pandas as pd
import numpy as np
import gspread
from google.oauth2.service_account import Credentials
import datetime

# =====================================================================
# 🛠️ KONFIGURASI HALAMAN & STYLE UTAMA
# =====================================================================
st.set_page_config(
    page_title="Dashboard Performa Affiliate & Meta Ads",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS untuk menyeragamkan visual metrik dan elemen tabel
st.markdown("""
    <style>
    [data-testid="stMetricValue"] {
        font-size: 22px !important;
        font-weight: bold;
    }
    div.stButton > button:first-child {
        background-color: #007bff;
        color: white;
        border-radius: 5px;
    }
    .main-header {
        font-size: 28px;
        font-weight: bold;
        color: #1E3A8A;
        margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# =====================================================================
# 💾 KONEKSI DATABASE (GOOGLE SHEETS INTEGRATION WITH GSPREAD)
# =====================================================================
@st.cache_resource(ttl=600)
def init_gspread():
    """Inisialisasi koneksi ke Google Sheets menggunakan Streamlit Secrets."""
    try:
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        # Mengambil kredensial dari Streamlit Secrets
        creds_dict = dict(st.secrets["gspread_credentials"])
        # Handle escape character untuk private key
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(credentials)
        
        spreadsheet_name = st.secrets["google_sheets"]["spreadsheet_name"]
        sheet = client.open(spreadsheet_name)
        return sheet
    except Exception as e:
        st.error(f"Gagal terhubung ke Google Sheets: {str(e)}")
        return None

def verify_and_init_headers(sheet):
    """Memastikan 3 worksheet utama ada beserta struktur headernya."""
    # 1. Worksheet Riwayat_Summary
    try:
        ws_summary = sheet.worksheet("Riwayat_Summary")
    except gspread.exceptions.WorksheetNotFound:
        ws_summary = sheet.add_worksheet(title="Riwayat_Summary", rows="1000", cols="10")
        
    if not ws_summary.row_values(1):
        ws_summary.append_row(["Tanggal", "Nama Laporan", "Spend", "Komisi Iklan", "Komisi Organik", "Total Komisi Nett", "Profit"])

    # 2. Worksheet Riwayat_Tag
    try:
        ws_tag = sheet.worksheet("Riwayat_Tag")
    except gspread.exceptions.WorksheetNotFound:
        ws_tag = sheet.add_worksheet(title="Riwayat_Tag", rows="5000", cols="15")
        
    if not ws_tag.row_values(1):
        ws_tag.append_row(["Nama Laporan", "Tipe", "Clean_Tag", "Spend", "Klik_Meta", "Klik_Shopee", "Pesanan", "Kebocoran", "Komisi_Kotor", "Komisi_Bersih", "Profit_Rugi", "ROAS"])

    # 3. Worksheet Raw_Sales
    try:
        ws_sales = sheet.worksheet("Raw_Sales")
    except gspread.exceptions.WorksheetNotFound:
        ws_sales = sheet.add_worksheet(title="Raw_Sales", rows="10000", cols="10")
        
    if not ws_sales.row_values(1):
        ws_sales.append_row(["Nama Laporan", "Clean_Tag", "Nama Produk", "Kategori", "Item Terjual", "Komisi"])

# Inisialisasi Google Sheet
gc_sheet = init_gspread()
if gc_sheet:
    verify_and_init_headers(gc_sheet)

# =====================================================================
# 🛠️ LOGIKA PENCARIAN KOLOM & PEMBERSIHAN DATA (SAKTI)
# =====================================================================
def clean_tag_value(val):
    """Pembersihan tag sesuai aturan bisnis."""
    if pd.isna(val) or str(val).strip() == "" or str(val).lower() == "nan":
        return "Organik"
    s = str(val).strip()
    if s.startswith("#"):
        s = s[1:]
    if s.endswith("----"):
        s = s[:-4]
    return s if s != "" else "Organik"

def clean_numeric(val):
    """Mengubah format string mata uang/angka menjadi float secara aman."""
    if pd.isna(val):
        return 0.0
    s = str(val).strip().replace("Rp", "").replace("%", "").replace(" ", "")
    if not s:
        return 0.0
    try:
        if "," in s and "." in s:
            if s.find(".") < s.find(","): 
                s = s.replace(".", "").replace(",", ".")
            else: 
                s = s.replace(",", "")
        elif "," in s and "." not in s:
            parts = s.split(",")
            if len(parts[-1]) == 2:
                s = s.replace(",", ".")
            else:
                s = s.replace(",", "")
        return float(s)
    except ValueError:
        return 0.0

def find_column_by_keywords(df, keywords):
    """Mencari nama kolom asli di dataframe berdasarkan rumpun kata kunci."""
    for col in df.columns:
        col_lower = str(col).lower().strip()
        for kw in keywords:
            if kw in col_lower:
                return col
    return None

# =====================================================================
# 🚀 PROSES INGESTI & PENGGABUNGAN DATA MULTI-FILE
# =====================================================================
def process_affiliate_data(uploaded_files, report_date, report_name):
    """Memproses kombinasi file Meta Ads dan Shopee Affiliate (hingga 5 file)."""
    meta_df = pd.DataFrame()
    shopee_click_dfs = []
    shopee_commission_dfs = []
    
    for f in uploaded_files:
        try:
            df_temp = pd.read_csv(f, nrows=5)
            f.seek(0)
            df_full = pd.read_csv(f)
        except Exception as e:
            st.error(f"Gagal membaca file {f.name}: {str(e)}")
            continue
            
        cols_lower = [str(c).lower() for c in df_full.columns]
        
        if any("spend" in cl or "jumlah yang dibelanjakan" in cl or "biaya" in cl for cl in cols_lower):
            meta_df = df_full
            st.toast(f"Berhasil mendeteksi file Meta Ads: {f.name}", icon="📢")
        elif any("click time" in cl or "waktu klik" in cl or "sub id" in cl or "tag" in cl for cl in cols_lower) and any("klik" in cl or "click" in cl or "link" in cl for cl in cols_lower):
            shopee_click_dfs.append(df_full)
            st.toast(f"Berhasil mendeteksi Klik Shopee: {f.name}", icon="🔗")
        elif any("komisi" in cl or "commission" in cl or "nama produk" in cl or "product name" in cl or "nama barange" in cl for cl in cols_lower):
            shopee_commission_dfs.append(df_full)
            st.toast(f"Berhasil mendeteksi Komisi Shopee: {f.name}", icon="💰")
        else:
            if find_column_by_keywords(df_full, ["spend", "dibelanjakan", "cost"]):
                meta_df = df_full
            elif find_column_by_keywords(df_full, ["nama produk", "product name", "nama barange"]):
                shopee_commission_dfs.append(df_full)
            else:
                shopee_click_dfs.append(df_full)
                
    if meta_df.empty and not shopee_commission_dfs:
        st.error("Proses dibatalkan. Anda harus mengunggah setidaknya file Meta Ads atau file Komisi Shopee.")
        return False
        
    # --- 1. PROSES DATA META ADS ---
    meta_cleaned = pd.DataFrame(columns=["Clean_Tag", "Spend", "Klik_Meta"])
    if not meta_df.empty:
        col_meta_name = find_column_by_keywords(meta_df, ["nama iklan", "ad name", "iklan"])
        col_meta_spend = find_column_by_keywords(meta_df, ["spend", "jumlah yang dibelanjakan", "biaya", "cost"])
        col_meta_click = find_column_by_keywords(meta_df, ["klik tautan", "link clicks", "klik"])
        
        if col_meta_name and col_meta_spend:
            meta_df["Clean_Tag"] = meta_df[col_meta_name].apply(clean_tag_value)
            meta_df["Spend_Cleaned"] = meta_df[col_meta_spend].apply(clean_numeric)
            if col_meta_click:
                meta_df["Klik_Cleaned"] = meta_df[col_meta_click].apply(clean_numeric)
            else:
                meta_df["Klik_Cleaned"] = 0.0
                
            meta_grouped = meta_df.groupby("Clean_Tag").agg(
                Spend=("Spend_Cleaned", "sum"),
                Klik_Meta=("Klik_Cleaned", "sum")
            ).reset_index()
            meta_cleaned = meta_grouped
        else:
            st.warning("Struktur kolom file Meta Ads tidak sesuai standar dinamis. Kolom Spend/Nama Iklan gagal dideteksi.")

    # --- 2. PROSES DATA KLIK SHOPEE (APPEND MULTI-AKUN) ---
    shopee_clicks_all = pd.DataFrame()
    if shopee_click_dfs:
        combined_click = pd.concat(shopee_click_dfs, ignore_index=True)
        col_shopee_tag = find_column_by_keywords(combined_click, ["sub id 1", "sub_id_1", "tag iklan", "sub id", "link id"])
        if not col_shopee_tag:
            col_shopee_tag = combined_click.columns[0]
            
        combined_click["Clean_Tag"] = combined_click[col_shopee_tag].apply(clean_tag_value)
        shopee_clicks_all = combined_click.groupby("Clean_Tag").size().reset_index(name="Klik_Shopee")

    # --- 3. PROSES DATA KOMISI SHOPEE (APPEND & MERGE MULTI-AKUN) ---
    shopee_comm_all = pd.DataFrame()
    raw_sales_list = []
    
    if shopee_commission_dfs:
        combined_comm = pd.concat(shopee_commission_dfs, ignore_index=True)
        
        col_prod_name = find_column_by_keywords(combined_comm, ['nama produk', 'product name', 'info produk', 'nama barange'])
        col_category = find_column_by_keywords(combined_comm, ['kategori', 'l1 kategori'])
        col_qty = find_column_by_keywords(combined_comm, ['item terjual', 'jumlah', 'qty', 'jumlah item'])
        col_commission = find_column_by_keywords(combined_comm, ['komisi bersih', 'net commission', 'nett commission', 'komisi'])
        col_comm_tag = find_column_by_keywords(combined_comm, ['sub id 1', 'sub_id_1', 'tag', 'sub id'])
        col_gross_comm = find_column_by_keywords(combined_comm, ['total komisi', 'gross commission', 'komisi kotor'])
        
        if not col_prod_name: col_prod_name = combined_comm.columns[0]
        if not col_category: combined_comm["Kategori_Dummy"] = "Umum"; col_category = "Kategori_Dummy"
        if not col_qty: combined_comm["Qty_Dummy"] = 1; col_qty = "Qty_Dummy"
        if not col_commission: col_commission = combined_comm.columns[-1]
        if not col_comm_tag:
            combined_comm["Tag_Dummy"] = "Organik"
            col_comm_tag = "Tag_Dummy"
            
        combined_comm["Clean_Tag"] = combined_comm[col_comm_tag].apply(clean_tag_value)
        combined_comm["Qty_Cleaned"] = combined_comm[col_qty].apply(clean_numeric)
        combined_comm["Comm_Cleaned"] = combined_comm[col_commission].apply(clean_numeric)
        
        if col_gross_comm:
            combined_comm["Gross_Comm_Cleaned"] = combined_comm[col_gross_comm].apply(clean_numeric)
        else:
            combined_comm["Gross_Comm_Cleaned"] = combined_comm["Comm_Cleaned"]

        shopee_comm_all = combined_comm.groupby("Clean_Tag").agg(
            Pesanan=("Qty_Cleaned", "sum"),
            Komisi_Kotor=("Gross_Comm_Cleaned", "sum"),
            Komisi_Bersih=("Comm_Cleaned", "sum")
        ).reset_index()
        
        for _, row in combined_comm.iterrows():
            raw_sales_list.append([
                report_name,
                row["Clean_Tag"],
                str(row[col_prod_name]),
                str(row[col_category]),
                int(row["Qty_Cleaned"]),
                float(row["Comm_Cleaned"])
            ])

    # --- 4. MASTER MERGE ALL DATA (META + SHOPEE CLICK + SHOPEE COMM) ---
    all_tags = set(meta_cleaned["Clean_Tag"].unique()) if not meta_cleaned.empty else set()
    if not shopee_clicks_all.empty:
        all_tags.update(shopee_clicks_all["Clean_Tag"].unique())
    if not shopee_comm_all.empty:
        all_tags.update(shopee_comm_all["Clean_Tag"].unique())
        
    master_tag_df = pd.DataFrame(list(all_tags), columns=["Clean_Tag"])
    
    if not meta_cleaned.empty:
        master_tag_df = master_tag_df.merge(meta_cleaned, on="Clean_Tag", how="left")
    else:
        master_tag_df["Spend"] = 0.0
        master_tag_df["Klik_Meta"] = 0.0
        
    if not shopee_clicks_all.empty:
        master_tag_df = master_tag_df.merge(shopee_clicks_all, on="Clean_Tag", how="left")
    else:
        master_tag_df["Klik_Shopee"] = 0.0
        
    if not shopee_comm_all.empty:
        master_tag_df = master_tag_df.merge(shopee_comm_all, on="Clean_Tag", how="left")
    else:
        master_tag_df["Pesanan"] = 0.0
        master_tag_df["Komisi_Kotor"] = 0.0
        master_tag_df["Komisi_Bersih"] = 0.0
        
    master_tag_df.fillna(0, inplace=True)
    
    master_tag_df["Nama Laporan"] = report_name
    master_tag_df["Tipe"] = master_tag_df["Clean_Tag"].apply(lambda x: "Organik" if x == "Organik" else "Iklan")
    master_tag_df["Profit_Rugi"] = master_tag_df["Komisi_Bersih"] - master_tag_df["Spend"]
    
    master_tag_df["ROAS"] = master_tag_df.apply(
        lambda r: round(r["Komisi_Bersih"] / r["Spend"], 2) if r["Spend"] > 0 else 0.0, axis=1
    )
    master_tag_df["Kebocoran"] = master_tag_df.apply(
        lambda r: round(((r["Klik_Meta"] - r["Klik_Shopee"]) / r["Klik_Meta"]) * 100, 2) if r["Klik_Meta"] > 0 else 0.0, axis=1
    )
    
    riwayat_tag_rows = master_tag_df[[
        "Nama Laporan", "Tipe", "Clean_Tag", "Spend", "Klik_Meta", "Klik_Shopee", 
        "Pesanan", "Kebocoran", "Komisi_Kotor", "Komisi_Bersih", "Profit_Rugi", "ROAS"
    ]].values.tolist()
    
    # --- 5. KALKULASI DATA SUMMARY HARIAN ---
    total_spend = master_tag_df["Spend"].sum()
    komisi_iklan = master_tag_df[master_tag_df["Tipe"] == "Iklan"]["Komisi_Bersih"].sum()
    komisi_organik = master_tag_df[master_tag_df["Tipe"] == "Organik"]["Komisi_Bersih"].sum()
    total_komisi_nett = master_tag_df["Komisi_Bersih"].sum()
    total_profit = total_komisi_nett - total_spend
    
    riwayat_summary_row = [
        str(report_date),
        report_name,
        float(total_spend),
        float(komisi_iklan),
        float(komisi_organik),
        float(total_komisi_nett),
        float(total_profit)
    ]
    
    # --- 6. SIMPAN PERMANEN KE GOOGLE SHEETS ---
    if gc_sheet:
        try:
            ws_sum = gc_sheet.worksheet("Riwayat_Summary")
            ws_tag = gc_sheet.worksheet("Riwayat_Tag")
            ws_sal = gc_sheet.worksheet("Raw_Sales")
            
            ws_sum.append_row(riwayat_summary_row)
            ws_tag.append_rows(riwayat_tag_rows)
            if raw_sales_list:
                ws_sal.append_rows(raw_sales_list)
                
            return True
        except Exception as e:
            st.error(f"Gagal menulis data ke Google Sheets: {str(e)}")
            return False
    else:
        st.error("Database cloud tidak tersedia.")
        return False

# =====================================================================
# 📊 UTILITY MENGAMBIL DATA DARI CLOUD DATABASE
# =====================================================================
def load_cloud_data():
    """Mengambil seluruh data dari Google Sheets secara realtime."""
    if not gc_sheet:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    try:
        df_sum = pd.DataFrame(gc_sheet.worksheet("Riwayat_Summary").get_all_records())
        df_tag = pd.DataFrame(gc_sheet.worksheet("Riwayat_Tag").get_all_records())
        df_sal = pd.DataFrame(gc_sheet.worksheet("Raw_Sales").get_all_records())
        return df_sum, df_tag, df_sal
    except Exception as e:
        st.warning(f"Koneksi database kosong atau gagal memuat data: {str(e)}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# =====================================================================
# INTERFACE UTAMA DASHBOARD STREAMLIT
# =====================================================================
st.markdown('<div class="main-header">📊 Dashboard Evaluasi & Performa Affiliate Multi-Akun</div>', unsafe_allow_html=True)

df_summary, df_tag, df_sales = load_cloud_data()

with st.sidebar:
    st.header("📥 Ingesti Data Baru")
    input_tgl = st.date_input("Tanggal Operasional Laporan", datetime.date.today())
    input_nama_laporan = st.text_input("Nama Laporan / Batch", f"Batch_{input_tgl.strftime('%Y%m%d')}")
    
    uploaded_files = st.file_uploader(
        "Upload File CSV (Maks 5 File)", 
        type=["csv"], 
        accept_multiple_files=True
    )
    
    if st.button("🚀 Proses Data & Sinkronisasi"):
        if not uploaded_files:
            st.error("Silakan unggah berkas CSV terlebih dahulu.")
        elif len(uploaded_files) > 5:
            st.error("Maksimal berkas yang diunggah sekaligus adalah 5 file.")
        else:
            with st.spinner("Sedang memproses, membersihkan, dan mengunggah data ke database cloud..."):
                sukses = process_affiliate_data(uploaded_files, input_tgl, input_nama_laporan)
                if sukses:
                    st.success("Data sukses diintegrasikan ke Google Sheets!")
                    st.rerun()

# --- BAGIAN 2: FILTER PERIODE DENGAN TOMBOL CEPAT ---
st.subheader("📅 Filter Rentang Analisis Performa")
col_btn1, col_btn2, col_btn3, col_date = st.columns([1, 1, 1, 4])

today = datetime.date.today()
start_date = today - datetime.timedelta(days=30)
end_date = today

with col_btn1:
    if st.button("⏱️ Kemarin", use_container_width=True):
        start_date = today - datetime.timedelta(days=1)
        end_date = today - datetime.timedelta(days=1)
with col_btn2:
    if st.button("📅 Bulan Ini", use_container_width=True):
        start_date = today.replace(day=1)
        end_date = today
with col_btn3:
    if st.button("⏮️ Bulan Lalu", use_container_width=True):
        last_month = today.replace(day=1) - datetime.timedelta(days=1)
        start_date = last_month.replace(day=1)
        end_date = last_month

with col_date:
    date_range = st.date_input(
        "Kustom Tanggal Evaluasi",
        value=(start_date, end_date),
        label_visibility="collapsed"
    )

if isinstance(date_range, tuple) and len(date_range) == 2:
    fil_start, fil_end = date_range
else:
    fil_start, fil_end = start_date, end_date

if not df_summary.empty and "Tanggal" in df_summary.columns:
    df_summary["Tanggal_Parsed"] = pd.to_datetime(df_summary["Tanggal"]).dt.date
    df_filtered_summary = df_summary[(df_summary["Tanggal_Parsed"] >= fil_start) & (df_summary["Tanggal_Parsed"] <= fil_end)]
else:
    df_filtered_summary = pd.DataFrame()

if not df_filtered_summary.empty and not df_tag.empty:
    laporan_aktif = df_filtered_summary["Nama Laporan"].unique()
    df_filtered_tag = df_tag[df_tag["Nama Laporan"].isin(laporan_aktif)]
    df_filtered_sales = df_sales[df_sales["Nama Laporan"].isin(laporan_aktif)] if not df_sales.empty else pd.DataFrame()
else:
    df_filtered_tag = pd.DataFrame()
    df_filtered_sales = pd.DataFrame()

# =====================================================================
# 📊 KOTAK METRIK RINGKASAN UTAMA (FINANSIAL MAKRO)
# =====================================================================
st.write("---")
st.subheader("📈 Ringkasan Eksekutif Finansial (Periode Terpilih)")

if not df_filtered_summary.empty:
    m_spend = df_filtered_summary["Spend"].sum()
    m_kom_iklan = df_filtered_summary["Komisi Iklan"].sum()
    m_kom_org = df_filtered_summary["Komisi Organik"].sum()
    m_profit_iklan = m_kom_iklan - m_spend
    m_total_profit = df_filtered_summary["Profit"].sum()
else:
    m_spend = m_kom_iklan = m_kom_org = m_profit_iklan = m_total_profit = 0.0

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric(label="💵 Total Spend Iklan", value=f"Rp {m_spend:,.0f}")
m2.metric(label="🛍️ Komisi Iklan Nett", value=f"Rp {m_kom_iklan:,.0f}")
m3.metric(label="🌱 Komisi Organik", value=f"Rp {m_kom_org:,.0f}")
m4.metric(
    label="📊 Keuntungan Iklan", 
    value=f"Rp {m_profit_iklan:,.0f}",
    delta=f"{round((m_kom_iklan/m_spend)*100,1)}% ROAS" if m_spend > 0 else "0% ROAS",
    delta_color="normal" if m_profit_iklan >= 0 else "inverse"
)
m5.metric(
    label="🏆 Keuntungan Bersih (All)", 
    value=f"Rp {m_total_profit:,.0f}",
    delta="Profit" if m_total_profit >= 0 else "Rugi",
    delta_color="normal" if m_total_profit >= 0 else "inverse"
)

# =====================================================================
# 📋 RIWAYAT LAPORAN HARIAN & MANAJEMEN DATA CLOUD
# =====================================================================
st.write("---")
st.subheader("🗂️ Riwayat Laporan Terdaftar di Cloud")

if not df_filtered_summary.empty:
    df_display_sum = df_filtered_summary[["Tanggal", "Nama Laporan", "Spend", "Komisi Iklan", "Komisi Organik", "Total Komisi Nett", "Profit"]]
    df_display_sum = df_display_sum.reset_index(drop=True)
    
    st.dataframe(df_display_sum, use_container_width=True)
    
    with st.expander("⚠️ Zona Bahaya - Hapus Laporan dari Cloud"):
        laporan_to_delete = st.multiselect("Pilih Nama Laporan yang Ingin Dihapus Permanen:", df_summary["Nama Laporan"].unique())
        if st.button("🗑️ Hapus Laporan Terpilih"):
            if not laporan_to_delete:
                st.warning("Pilih minimal satu laporan untuk dihapus.")
            elif gc_sheet:
                with st.spinner("Sedang membersihkan data dari Google Sheets..."):
                    try:
                        ws_s = gc_sheet.worksheet("Riwayat_Summary")
                        records_s = ws_s.get_all_records()
                        for idx, row in reversed(list(enumerate(records_s, start=2))):
                            if row["Nama Laporan"] in laporan_to_delete:
                                ws_s.delete_rows(idx)
                                
                        ws_t = gc_sheet.worksheet("Riwayat_Tag")
                        records_t = ws_t.get_all_records()
                        for idx, row in reversed(list(enumerate(records_t, start=2))):
                            if row["Nama Laporan"] in laporan_to_delete:
                                ws_t.delete_rows(idx)
                                
                        ws_sl = gc_sheet.worksheet("Raw_Sales")
                        records_sl = ws_sl.get_all_records()
                        for idx, row in reversed(list(enumerate(records_sl, start=2))):
                            if row["Nama Laporan"] in laporan_to_delete:
                                ws_sl.delete_rows(idx)
                                
                        st.success("Data laporan berhasil dihapus secara permanen dari Cloud!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Gagal menghapus data: {str(e)}")
else:
    st.info("Tidak ada riwayat data pada rentang tanggal terpilih.")

# =====================================================================
# 📊 HASIL BEDAH DATA RINCI PER TAG (AKTIF & ORGANIK)
# =====================================================================
st.write("---")
st.subheader("🔍 Bedah Kinerja Rinci Berdasarkan Tag Referensi")

if not df_filtered_tag.empty:
    t_kl_meta = df_filtered_tag["Klik_Meta"].sum()
    t_kl_shop = df_filtered_tag["Klik_Shopee"].sum()
    t_pesanan = df_filtered_tag["Pesanan"].sum()
    t_spend_iklan = df_filtered_tag["Spend"].sum()
    t_kom_bersih = df_filtered_tag["Komisi_Bersih"].sum()
    
    avg_roas = round(t_kom_bersih / t_spend_iklan, 2) if t_spend_iklan > 0 else 0.0
    avg_leakage = round(((t_kl_meta - t_kl_shop) / t_kl_meta) * 100, 2) if t_kl_meta > 0 else 0.0
    
    st.markdown("#### **Metrik Operasional Agregat**")
    o1, o2, o3, o4, o5 = st.columns(5)
    o1.metric("🖱️ Total Klik Meta", f"{t_kl_meta:,.0f} Klik")
    o2.metric("🔗 Total Klik Shopee", f"{t_kl_shop:,.0f} Klik")
    o3.metric("📦 Total Pesanan Terjadi", f"{t_pesanan:,.0f} Item")
    o4.metric("📈 ROAS Agregat Iklan", f"{avg_roas}x")
    o5.metric(
        "💧 Rata-rata Kebocoran Klik", 
        f"{avg_leakage}%", 
        delta=f"{t_kl_meta - t_kl_shop:,.0f} Klik Hilang",
        delta_color="inverse"
    )
    
    df_iklan_aktif = df_filtered_tag[df_filtered_tag["Tipe"] == "Iklan"].reset_index(drop=True)
    df_organik = df_filtered_tag[df_filtered_tag["Tipe"] == "Organik"].reset_index(drop=True)
    
    st.write(" ")
    st.markdown("### 🟢 Kelompok Iklan Aktif (Meta Ads)")
    st.write("Klik salah satu baris pada tabel iklan aktif di bawah untuk membedah produk retail yang terjual:")
    
    selected_iklan = st.dataframe(
        df_iklan_aktif[["Clean_Tag", "Spend", "Klik_Meta", "Klik_Shopee", "Pesanan", "Kebocoran", "Komisi_Bersih", "Profit_Rugi", "ROAS"]],
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row"
    )
    
    st.markdown("### 🍂 Kelompok Lalu Lintas Organik / Tag Tidak Aktif")
    st.write("Klik salah satu baris pada tabel organik untuk melihat detail produk:")
    selected_organik = st.dataframe(
        df_organik[["Clean_Tag", "Klik_Shopee", "Pesanan", "Komisi_Bersih"]],
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row"
    )
    
    chosen_tag = None
    
    if selected_iklan and "selection" in selected_iklan and selected_iklan["selection"]["rows"]:
        row_idx = selected_iklan["selection"]["rows"][0]
        chosen_tag = df_iklan_aktif.loc[row_idx, "Clean_Tag"]
    elif selected_organik and "selection" in selected_organik and selected_organik["selection"]["rows"]:
        row_idx = selected_organik["selection"]["rows"][0]
        chosen_tag = df_organik.loc[row_idx, "Clean_Tag"]

    # =====================================================================
    # 🛍️ DETAIL PRODUK TERJUAL (PALING BAWAH - DRILL DOWN ANALYSIS)
    # =====================================================================
    st.write("---")
    st.subheader("🛍️ Rincian Produk Retail Terjual (Drill-Down)")
    
    if chosen_tag:
        st.info(f"Menampilkan produk yang terjual untuk Tag Akun: **{chosen_tag}**")
        if not df_filtered_sales.empty:
            df_tag_sales = df_filtered_sales[df_filtered_sales["Clean_Tag"] == chosen_tag]
            if not df_tag_sales.empty:
                df_sales_summary = df_tag_sales.groupby(["Nama Produk", "Kategori"]).agg(
                    Total_Terjual=("Item Terjual", "sum"),
                    Total_Komisi=("Komisi", "sum")
                ).reset_index().sort_values(by="Total_Terjual", ascending=False)
                
                st.dataframe(df_sales_summary, use_container_width=True)
            else:
                st.warning("Tidak ditemukan rincian item produk terjual untuk tag ini di database.")
        else:
            st.warning("Data Raw Sales kosong di database.")
    else:
        st.markdown("*Silakan klik salah satu baris tag pada tabel Kelompok Iklan Aktif atau Organik di atas untuk menampilkan detail item barang yang laku.*")
else:
    st.info("Belum ada data detail performa tag untuk ditampilkan. Silakan unggah laporan baru via sidebar.")
