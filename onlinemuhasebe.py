from datetime import datetime
import os
import sqlite3
import hashlib
import json
import pandas as pd
import streamlit as st

# Sayfa Ayarları
st.set_page_config(
    page_title="Bireysel Muhasebe Platformu",
    page_icon="⚖️",
    layout="wide"
)

# Kendi Yönetici E-Posta Adresini buraya yazmalısın:
ADMIN_EMAIL = "admin@kalkanmuhasebe.com"

# Şifreleri güvenli saklamak için hashleme fonksiyonu
def hash_sifre(sifre):
    return hashlib.sha256(sifre.encode()).hexdigest()

# Veritabanı ve Tabloları Başlatma
def init_db():
    conn = sqlite3.connect("muhasebe.db")
    cursor = conn.cursor()
    
    # 1. Kullanıcılar Tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kullanicilar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            sifre TEXT
        )
    """)
    
    # 2. Banka Hesapları
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bankalar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            ad TEXT,
            bakiye REAL,
            FOREIGN KEY(user_id) REFERENCES kullanicilar(id)
        )
    """)
    
    # 3. Kredi Kartları
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kartlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            ad TEXT,
            limit_tutar REAL,
            kullanilabilir_tutar REAL,
            FOREIGN KEY(user_id) REFERENCES kullanicilar(id)
        )
    """)
    
    # 4. Dışarıdaki Alacaklar
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alacaklar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            ad TEXT,
            tutar REAL,
            FOREIGN KEY(user_id) REFERENCES kullanicilar(id)
        )
    """)
    
    # 5. Diğer Borçlar
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS borclar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            ad TEXT,
            tutar REAL,
            FOREIGN KEY(user_id) REFERENCES kullanicilar(id)
        )
    """)

    conn.commit()
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect("muhasebe.db")
    return conn, conn.cursor()

# Oturum Durumu Kontrolü
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["user_id"] = None
    st.session_state["email"] = None

# ---------------------------------------------------------
# GİRİŞ / KAYIT EKRANI
# ---------------------------------------------------------
if not st.session_state["logged_in"]:
    st.title("🔐 Bireysel Muhasebe - Giriş")
    st.caption("Varlıklarınızı, borçlarınızı ve net durumunuzu güvenle takip edin.")
    
    secim = st.selectbox("İşlem Seçin", ["Giriş Yap", "Kayıt Ol"])
    
    if secim == "Kayıt Ol":
        st.subheader("Yeni Hesap Oluştur")
        yeni_email = st.text_input("E-Posta Adresi").strip().lower()
        yeni_sifre = st.text_input("Şifre", type="password")
        yeni_sifre_tekrar = st.text_input("Şifre (Tekrar)", type="password")
        
        if st.button("KAYIT OL"):
            if not yeni_email or not yeni_sifre:
                st.warning("Lütfen tüm alanları doldurun!")
            elif yeni_sifre != yeni_sifre_tekrar:
                st.error("Şifreler birbiriyle eşleşmiyor!")
            else:
                try:
                    conn, cursor = get_db()
                    cursor.execute(
                        "INSERT INTO kullanicilar (email, sifre) VALUES (?, ?)",
                        (yeni_email, hash_sifre(yeni_sifre))
                    )
                    conn.commit()
                    conn.close()
                    st.success("Kayıt başarılı! Şimdi 'Giriş Yap' sekmesinden giriş yapabilirsiniz.")
                except sqlite3.IntegrityError:
                    st.error("Bu e-posta adresi zaten kayıtlı!")
                    
    else: # Giriş Yap
        st.subheader("Hesabınıza Giriş Yapın")
        giris_email = st.text_input("E-Posta Adresi").strip().lower()
        giris_sifre = st.text_input("Şifre", type="password")
        
        if st.button("GİRİŞ YAP"):
            conn, cursor = get_db()
            cursor.execute(
                "SELECT id, email, sifre FROM kullanicilar WHERE email = ?",
                (giris_email,)
            )
            user = cursor.fetchone()
            conn.close()
            
            if user and user[2] == hash_sifre(giris_sifre):
                st.session_state["logged_in"] = True
                st.session_state["user_id"] = user[0]
                st.session_state["email"] = user[1]
                st.success("Giriş başarılı!")
                st.rerun()
            else:
                st.error("Hatalı e-posta veya şifre!")

# ---------------------------------------------------------
# ANA UYGULAMA (Giriş Yapıldıysa)
# ---------------------------------------------------------
else:
    current_user_id = st.session_state["user_id"]
    current_email = st.session_state["email"]
    is_admin = (current_email == ADMIN_EMAIL.lower())

    # Üst Bilgi Alanı
    col_baslik, col_cikis = st.columns([5, 1])
    with col_baslik:
        st.title("⚖️ Bireysel Muhasebe")
        if is_admin:
            st.caption(f"Aktif Hesap: **{current_email}** (👑 **YÖNETİCİ**)")
        else:
            st.caption(f"Aktif Hesap: **{current_email}**")
    with col_cikis:
        if st.button("Çıkış Yap"):
            st.session_state["logged_in"] = False
            st.session_state["user_id"] = None
            st.session_state["email"] = None
            st.rerun()

    st.divider()

    # Verileri Çekme ve Genel Finansal Durum Hesabı
    conn, cursor = get_db()

    cursor.execute("SELECT id, ad, bakiye FROM bankalar WHERE user_id = ?", (current_user_id,))
    bankalar = cursor.fetchall()

    cursor.execute("SELECT id, ad, limit_tutar, kullanilabilir_tutar FROM kartlar WHERE user_id = ?", (current_user_id,))
    kartlar = cursor.fetchall()

    cursor.execute("SELECT id, ad, tutar FROM alacaklar WHERE user_id = ?", (current_user_id,))
    alacaklar = cursor.fetchall()

    cursor.execute("SELECT id, ad, tutar FROM borclar WHERE user_id = ?", (current_user_id,))
    borclar = cursor.fetchall()

    conn.close()

    bank_total = sum(b[2] for b in bankalar)
    receivable_total = sum(a[2] for a in alacaklar)
    card_debt_total = sum(max(0, k[2] - k[3]) for k in kartlar)
    debt_total = sum(d[2] for d in borclar)

    total_assets = bank_total + receivable_total
    total_debts = card_debt_total + debt_total
    net_status = total_assets - total_debts

    # Finansal Özet Kartları (Dashboard)
    m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
    m1.metric("Banka Hesapları", f"₺{bank_total:,.2f}")
    m2.metric("Dışarıdaki Alacaklar", f"₺{receivable_total:,.2f}")
    m3.metric("Kredi Kartı Borcu", f"₺{card_debt_total:,.2f}")
    m4.metric("Diğer Borçlar", f"₺{debt_total:,.2f}")
    m5.metric("Toplam Varlık", f"₺{total_assets:,.2f}")
    m6.metric("Toplam Borç", f"₺{total_debts:,.2f}")
    
    net_label = "Net Varlık" if net_status >= 0 else "Net Borç"
    m7.metric(net_label, f"₺{abs(net_status):,.2f}", delta=f"₺{net_status:,.2f}")

    st.divider()

    # Sekmeler
    tab_list = ["🏛️ BANKA HESAPLARI", "💳 KREDİ KARTLARI", "🤝 ALACAKLAR", "💸 DİĞER BORÇLAR", "💾 YEDEKLEME"]
    if is_admin:
        tab_list.append("👑 YÖNETİCİ PANELİ")

    tabs = st.tabs(tab_list)

    # -------------------- 1. BANKA HESAPLARI --------------------
    with tabs[0]:
        st.subheader("Banka Hesapları")
        with st.form("bank_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                b_name = st.text_input("Hesap Adı", placeholder="Örn. Maaş Hesabı")
            with col2:
                b_amount = st.number_input("Bakiye (TL)", min_value=0.0, step=100.0, format="%.2f")
            
            if st.form_submit_button("Hesap Ekle"):
                if not b_name:
                    st.warning("Lütfen hesap adını girin.")
                else:
                    conn, cursor = get_db()
                    cursor.execute("INSERT INTO bankalar (user_id, ad, bakiye) VALUES (?, ?, ?)", 
                                   (current_user_id, b_name, b_amount))
                    conn.commit()
                    conn.close()
                    st.success("Banka hesabı eklendi!")
                    st.rerun()

        if bankalar:
            df_b = pd.DataFrame(bankalar, columns=["ID", "Hesap Adı", "Bakiye (TL)"])
            df_b["Bakiye (TL)"] = df_b["Bakiye (TL)"].apply(lambda x: f"₺{x:,.2f}")
            st.dataframe(df_b, use_container_width=True)

            del_b_id = st.number_input("Silinecek Banka ID:", min_value=1, step=1, key="del_b")
            if st.button("Hesabı Sil", key="btn_del_b"):
                conn, cursor = get_db()
                cursor.execute("DELETE FROM bankalar WHERE id = ? AND user_id = ?", (del_b_id, current_user_id))
                conn.commit()
                conn.close()
                st.rerun()
        else:
            st.info("Henüz kayıtlı banka hesabı yok.")

    # -------------------- 2. KREDİ KARTLARI --------------------
    with tabs[1]:
        st.subheader("Kredi Kartları")
        st.caption("Kart borcu = Toplam Limit − Kullanılabilir Limit olarak otomatik hesaplanır.")
        
        with st.form("card_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                c_name = st.text_input("Kart Adı", placeholder="Örn. Ana Kredi Kartı")
            with col2:
                c_limit = st.number_input("Toplam Kart Limiti (TL)", min_value=0.0, step=500.0, format="%.2f")
            with col3:
                c_avail = st.number_input("Kullanılabilir Limit (TL)", min_value=0.0, step=500.0, format="%.2f")

            if st.form_submit_button("Kart Ekle"):
                if not c_name:
                    st.warning("Lütfen kart adını girin.")
                elif c_avail > c_limit:
                    st.error("Kullanılabilir limit, toplam kart limitinden büyük olamaz!")
                else:
                    conn, cursor = get_db()
                    cursor.execute("INSERT INTO kartlar (user_id, ad, limit_tutar, kullanilabilir_tutar) VALUES (?, ?, ?, ?)", 
                                   (current_user_id, c_name, c_limit, c_avail))
                    conn.commit()
                    conn.close()
                    st.success("Kredi kartı eklendi!")
                    st.rerun()

        if kartlar:
            card_data = []
            for k in kartlar:
                k_id, k_ad, k_lim, k_ava = k
                k_borc = max(0, k_lim - k_ava)
                card_data.append({
                    "ID": k_id,
                    "Kart Adı": k_ad,
                    "Toplam Limit": f"₺{k_lim:,.2f}",
                    "Kullanılabilir Limit": f"₺{k_ava:,.2f}",
                    "Hesaplanan Borç": f"₺{k_borc:,.2f}"
                })
            st.dataframe(pd.DataFrame(card_data), use_container_width=True)

            del_c_id = st.number_input("Silinecek Kart ID:", min_value=1, step=1, key="del_c")
            if st.button("Kartı Sil", key="btn_del_c"):
                conn, cursor = get_db()
                cursor.execute("DELETE FROM kartlar WHERE id = ? AND user_id = ?", (del_c_id, current_user_id))
                conn.commit()
                conn.close()
                st.rerun()
        else:
            st.info("Henüz kayıtlı kredi kartı yok.")

    # -------------------- 3. ALACAKLAR --------------------
    with tabs[2]:
        st.subheader("Dışarıdaki Alacaklar")
        with st.form("rec_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                r_name = st.text_input("Kişi / Açıklama", placeholder="Örn. Ahmet — verilen borç")
            with col2:
                r_amount = st.number_input("Kalan Alacak (TL)", min_value=0.0, step=100.0, format="%.2f")

            if st.form_submit_button("Alacak Ekle"):
                if not r_name:
                    st.warning("Lütfen açıklama girin.")
                else:
                    conn, cursor = get_db()
                    cursor.execute("INSERT INTO alacaklar (user_id, ad, tutar) VALUES (?, ?, ?)", 
                                   (current_user_id, r_name, r_amount))
                    conn.commit()
                    conn.close()
                    st.success("Alacak kaydı eklendi!")
                    st.rerun()

        if alacaklar:
            df_a = pd.DataFrame(alacaklar, columns=["ID", "Kişi / Açıklama", "Kalan Alacak (TL)"])
            df_a["Kalan Alacak (TL)"] = df_a["Kalan Alacak (TL)"].apply(lambda x: f"₺{x:,.2f}")
            st.dataframe(df_a, use_container_width=True)

            del_r_id = st.number_input("Silinecek Alacak ID:", min_value=1, step=1, key="del_r")
            if st.button("Alacağı Sil", key="btn_del_r"):
                conn, cursor = get_db()
                cursor.execute("DELETE FROM alacaklar WHERE id = ? AND user_id = ?", (del_r_id, current_user_id))
                conn.commit()
                conn.close()
                st.rerun()
        else:
            st.info("Henüz kayıtlı alacak yok.")

    # -------------------- 4. DİĞER BORÇLAR --------------------
    with tabs[3]:
        st.subheader("Diğer Borçlar")
        with st.form("debt_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                d_name = st.text_input("Kişi / Açıklama", placeholder="Örn. İhtiyaç kredisi")
            with col2:
                d_amount = st.number_input("Kalan Borç (TL)", min_value=0.0, step=100.0, format="%.2f")

            if st.form_submit_button("Borç Ekle"):
                if not d_name:
                    st.warning("Lütfen açıklama girin.")
                else:
                    conn, cursor = get_db()
                    cursor.execute("INSERT INTO borclar (user_id, ad, tutar) VALUES (?, ?, ?)", 
                                   (current_user_id, d_name, d_amount))
                    conn.commit()
                    conn.close()
                    st.success("Borç kaydı eklendi!")
                    st.rerun()

        if borclar:
            df_d = pd.DataFrame(borclar, columns=["ID", "Kişi / Açıklama", "Kalan Borç (TL)"])
            df_d["Kalan Borç (TL)"] = df_d["Kalan Borç (TL)"].apply(lambda x: f"₺{x:,.2f}")
            st.dataframe(df_d, use_container_width=True)

            del_d_id = st.number_input("Silinecek Borç ID:", min_value=1, step=1, key="del_d")
            if st.button("Borcu Sil", key="btn_del_d"):
                conn, cursor = get_db()
                cursor.execute("DELETE FROM borclar WHERE id = ? AND user_id = ?", (del_d_id, current_user_id))
                conn.commit()
                conn.close()
                st.rerun()
        else:
            st.info("Henüz kayıtlı borç yok.")

    # -------------------- 5. YEDEKLEME (JSON EXPORT/IMPORT) --------------------
    with tabs[4]:
        st.subheader("Yedekleme ve Aktarım")
        st.caption("Verileriniz bulut veritabanında saklanır. İsterseniz JSON formatında bilgisayarınıza indirebilirsiniz.")

        user_backup = {
            "banks": [{"name": b[1], "amount": b[2]} for b in bankalar],
            "cards": [{"name": k[1], "limit": k[2], "available": k[3]} for k in kartlar],
            "receivables": [{"name": a[1], "amount": a[2]} for a in alacaklar],
            "debts": [{"name": d[1], "amount": d[2]} for d in borclar]
        }

        json_str = json.dumps(user_backup, ensure_ascii=False, indent=2)
        st.download_button(
            label="📥 Yedeği İndir (JSON)",
            data=json_str,
            file_name=f"bireysel_muhasebe_yedek_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json"
        )

        st.markdown("---")
        st.write("📤 **Yedek Yükle**")
        uploaded_file = st.file_uploader("JSON yedek dosyanızı seçin", type=["json"])
        
        if uploaded_file is not None:
            if st.button("Yedeği Veritabanına Yükle"):
                try:
                    imp_data = json.load(uploaded_file)
                    conn, cursor = get_db()
                    
                    # Önce kullanıcının mevcut verilerini temizleyelim
                    cursor.execute("DELETE FROM bankalar WHERE user_id = ?", (current_user_id,))
                    cursor.execute("DELETE FROM kartlar WHERE user_id = ?", (current_user_id,))
                    cursor.execute("DELETE FROM alacaklar WHERE user_id = ?", (current_user_id,))
                    cursor.execute("DELETE FROM borclar WHERE user_id = ?", (current_user_id,))

                    # Yeni verileri yükleyelim
                    for b in imp_data.get("banks", []):
                        cursor.execute("INSERT INTO bankalar (user_id, ad, bakiye) VALUES (?, ?, ?)", (current_user_id, b["name"], b["amount"]))
                    for k in imp_data.get("cards", []):
                        cursor.execute("INSERT INTO kartlar (user_id, ad, limit_tutar, kullanilabilir_tutar) VALUES (?, ?, ?, ?)", (current_user_id, k["name"], k["limit"], k["available"]))
                    for a in imp_data.get("receivables", []):
                        cursor.execute("INSERT INTO alacaklar (user_id, ad, tutar) VALUES (?, ?, ?)", (current_user_id, a["name"], a["amount"]))
                    for d in imp_data.get("debts", []):
                        cursor.execute("INSERT INTO borclar (user_id, ad, tutar) VALUES (?, ?, ?)", (current_user_id, d["name"], d["amount"]))

                    conn.commit()
                    conn.close()
                    st.success("Yedek başarıyla yüklendi!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Yedek yüklenirken hata oluştu: {e}")

    # -------------------- 6. YÖNETİCİ PANELİ (Admin Only) --------------------
    if is_admin:
        with tabs[5]:
            st.subheader("👑 Yönetici Paneli")
            
            conn, cursor = get_db()
            cursor.execute("SELECT COUNT(*) FROM kullanicilar")
            u_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT id, email FROM kullanicilar ORDER BY id ASC")
            all_users = cursor.fetchall()
            conn.close()

            st.metric("Sistemdeki Toplam Kayıtlı Kullanıcı", u_count)
            st.markdown("---")
            
            if all_users:
                df_users = pd.DataFrame(all_users, columns=["Kullanıcı ID", "E-Posta Adresi"])
                st.dataframe(df_users, use_container_width=True)

                st.write("⚠️ **Kullanıcı Hesabı Silme**")
                del_user_id = st.number_input("Silmek İstediğiniz Kullanıcı ID:", min_value=1, step=1, key="del_u_admin")
                
                if st.button("Kullanıcıyı ve Tüm Verilerini Sil"):
                    if del_user_id == current_user_id:
                        st.error("Kendi yönetici hesabınızı buradan silemezsiniz!")
                    else:
                        conn, cursor = get_db()
                        cursor.execute("DELETE FROM bankalar WHERE user_id = ?", (del_user_id,))
                        cursor.execute("DELETE FROM kartlar WHERE user_id = ?", (del_user_id,))
                        cursor.execute("DELETE FROM alacaklar WHERE user_id = ?", (del_user_id,))
                        cursor.execute("DELETE FROM borclar WHERE user_id = ?", (del_user_id,))
                        cursor.execute("DELETE FROM kullanicilar WHERE id = ?", (del_user_id,))
                        conn.commit()
                        conn.close()
                        st.success(f"{del_user_id} ID'li kullanıcı tamamen silindi!")
                        st.rerun()