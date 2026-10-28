import streamlit as st
import pyodbc
import psycopg2
import pandas as pd
from groq import Groq

# ==========================================
# 1. KONFIGURASI (UBAH BAGIAN INI)
# ==========================================
# Mengambil Groq API Key
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]

# Mengambil konfigurasi SQL Server
db_config = st.secrets["postgres"]

# ==========================================
# 2. DEFINISI SKEMA DATABASE
# ==========================================
SKEMA_DB = """
Tabel: karyawan
Kolom: 
- id (INT)
- nama (VARCHAR) contoh: 'Budi Santoso'
- jabatan (VARCHAR) contoh: 'Data Engineer'
- gaji (INT) contoh: 12000000
"""

# ==========================================
# 3. FUNGSI-FUNGSI PENDUKUNG
# ==========================================
# def dapatkan_koneksi():
#     conn_str = f'DRIVER={DB_DRIVER};SERVER={DB_SERVER};DATABASE={DB_NAME};UID={DB_USER};PWD={DB_PASS}'
#     return pyodbc.connect(conn_str)

# def dapatkan_koneksi():
#   # Mengambil konfigurasi dari st.secrets["sql_server"]
#   driver = st.secrets["sql_server"]["driver"]
#   server = st.secrets["sql_server"]["server"]
#   database = st.secrets["sql_server"]["database"]
#   user = st.secrets["sql_server"]["user"]
#   password = st.secrets["sql_server"]["password"]

#   conn_str = f"DRIVER={driver};SERVER={server};DATABASE={database};UID={user};PWD={password};TrustServerCertificate=yes;"
#   return pyodbc.connect(conn_str)

def dapatkan_koneksi():
  conn = psycopg2.connect(
      host=db_config["host"],
      port=db_config["port"],
      database=db_config["database"],
      user=db_config["user"],
      password=db_config["password"],
      sslmode="require",  # Wajib diaktifkan untuk koneksi cloud aman
  )
  return conn

def eksekusi_sql_ke_dataframe(query):
    """Menjalankan query dan mengubahnya menjadi tabel Pandas"""
    try:
        conn = dapatkan_koneksi()
        # Menggunakan Pandas untuk membaca SQL langsung menjadi tabel (DataFrame)
        df = pd.read_sql(query, conn)
        conn.close()
        return df, None
    except Exception as e:
        return None, str(e)

def terjemahkan_ke_sql(pertanyaan, klien):
    """Meminta Groq mengubah bahasa Indonesia menjadi SQL Server query"""
    prompt = f"""
    Kamu adalah Data Engineer ahli SQL Server (T-SQL).
    Skema database: {SKEMA_DB}
    
    Buatkan query SQL untuk menjawab pertanyaan ini: "{pertanyaan}"
    PENTING: Hanya balas dengan sintaks SQL murni. Jangan gunakan markdown (```sql). Jangan beri penjelasan.
    """
    
    respon = klien.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0 # 0.0 agar jawaban presisi dan pasti
    )
    return respon.choices[0].message.content.strip()

# ==========================================
# 4. ANTARMUKA WEB (STREAMLIT UI)
# ==========================================
st.set_page_config(page_title="AI Data Engineer", layout="wide")
st.title("📊 Chatbot Database (Text-to-SQL)")
st.caption("Tanya database Anda menggunakan bahasa sehari-hari.")

# Inisialisasi Klien Groq


klien_groq = Groq(api_key=GROQ_API_KEY)

# Menyimpan riwayat pertanyaan di layar
if "riwayat_ui" not in st.session_state:
    st.session_state.riwayat_ui = []

# Tampilkan riwayat chat sebelumnya
for chat in st.session_state.riwayat_ui:
    with st.chat_message(chat["role"]):
        if chat["tipe"] == "teks":
            st.markdown(chat["konten"])
        elif chat["tipe"] == "tabel":
            st.dataframe(chat["konten"]) # Menampilkan tabel data
        elif chat["tipe"] == "kode":
            st.code(chat["konten"], language="sql")

# Kotak Input User
pertanyaan_user = st.chat_input("Contoh: Tampilkan total fuel consumed untuk unit Scania bulan ini")

if pertanyaan_user:
    # 1. Tampilkan pertanyaan user di UI
    with st.chat_message("user"):
        st.markdown(pertanyaan_user)
    st.session_state.riwayat_ui.append({"role": "user", "tipe": "teks", "konten": pertanyaan_user})
    
    # 2. Proses pembuatan SQL dan eksekusi
    with st.chat_message("assistant"):
        with st.spinner("Menerjemahkan ke SQL..."):
            query_sql = terjemahkan_ke_sql(pertanyaan_user, klien_groq)
            
            # Tampilkan query yang dihasilkan AI agar transparan
            st.markdown("**Query yang dihasilkan AI:**")
            st.code(query_sql, language="sql")
            st.session_state.riwayat_ui.append({"role": "assistant", "tipe": "kode", "konten": query_sql})
            
        with st.spinner("Mengambil data dari SQL Server..."):
            # Eksekusi query ke database
            df_hasil, error_msg = eksekusi_sql_ke_dataframe(query_sql)
            
            if error_msg:
                teks_error = f"❌ Terjadi kesalahan pada database:\n```\n{error_msg}\n```"
                st.error(teks_error)
                st.session_state.riwayat_ui.append({"role": "assistant", "tipe": "teks", "konten": teks_error})
            else:
                # Jika berhasil, tampilkan data dalam bentuk tabel interaktif
                st.markdown("**Hasil Data:**")
                st.dataframe(df_hasil, use_container_width=True)
                # Simpan tabel ke riwayat agar tidak hilang saat refresh
                st.session_state.riwayat_ui.append({"role": "assistant", "tipe": "tabel", "konten": df_hasil})