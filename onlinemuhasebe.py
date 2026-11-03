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
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kullanicilar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            sifre TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bankalar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            ad TEXT,
            bakiye REAL,
            FOREIGN KEY(user_id) REFERENCES kullanicilar(id)
        )
    """)
    
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
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alacaklar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            ad TEXT,
            tutar REAL,
            FOREIGN KEY(user_id) REFERENCES kullanicilar(id)
        )
    """)
    
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
                    
    else:
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
# ANA UYGULAMA
# ---------------------------------------------------------
else:
    current_user_id = st.session_state["user_id"]
    current_email = st.session_state["email"]
    is_admin = (current_email == ADMIN_EMAIL.lower())

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

    # Özet Kartları
    m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
    m1.metric("Banka Hesapları", f"₺{bank_total:,.2f}")
    m2.metric("Alacaklar", f"₺{receivable_total:,.2f}")
    m3.metric("Kart Borcu", f"₺{card_debt_total:,.2f}")
    m4.metric("Diğer Borçlar", f"₺{debt_total:,.2f}")
    m5.metric("Toplam Varlık", f"₺{total_assets:,.2f}")
    m6.metric("Toplam Borç", f"₺{total_debts:,.2f}")
    net_label = "Net Varlık" if net_status >= 0 else "Net Borç"
    m7.metric(net_label, f"₺{abs(net_status):,.2f}", delta=f"₺{net_status:,.2f}")

    st.divider()

    tab_list = ["🏛️ BANKA HESAPLARI", "💳 KREDİ KARTLARI", "🤝 ALACAKLAR", "💸 DİĞER BORÇLAR", "💾 YEDEKLEME"]
    if is_admin:
        tab_list.append("👑 YÖNETİCİ PANELİ")

    tabs = st.tabs(tab_list)

    # -------------------- 1. BANKA HESAPLARI --------------------
    with tabs[0]:
        st.subheader("Banka Hesapları Yönetimi")
        
        with st.form("bank_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                b_name = st.text_input("Hesap Adı", placeholder="Örn. Maaş Hesabı")
            with col2:
                b_amount = st.number_input("Bakiye (TL)", min_value=0.0, step=100.0, format="%.2f")
            if st.form_submit_button("Yeni Hesap Ekle"):
                if not b_name:
                    st.warning("Lütfen hesap adını girin.")
                else:
                    conn, cursor = get_db()
                    cursor.execute("INSERT INTO bankalar (user_id, ad, bakiye) VALUES (?, ?, ?)", (current_user_id, b_name, b_amount))
                    conn.commit()
                    conn.close()
                    st.success("Eklendi!")
                    st.rerun()

        if bankalar:
            st.dataframe(pd.DataFrame(bankalar, columns=["ID", "Hesap Adı", "Bakiye (TL)"]), use_container_width=True)
            
            st.markdown("---")
            col_duz, col_sil = st.columns(2)
            with col_duz:
                st.write("✏️ **Hesap Düzenle**")
                edit_b_id = st.number_input("Düzenlenecek Banka ID:", min_value=1, step=1, key="edit_b_id")
                new_b_name = st.text_input("Yeni Hesap Adı", key="new_b_name")
                new_b_amount = st.number_input("Yeni Bakiye (TL)", min_value=0.0, step=100.0, format="%.2f", key="new_b_amount")
                if st.button("Hesabı Güncelle"):
                    conn, cursor = get_db()
                    cursor.execute("UPDATE bankalar SET ad = ?, bakiye = ? WHERE id = ? AND user_id = ?", (new_b_name, new_b_amount, edit_b_id, current_user_id))
                    if cursor.rowcount > 0:
                        conn.commit()
                        st.success("Güncellendi!")
                        conn.close()
                        st.rerun()
                    else:
                        conn.close()
                        st.error("ID bulunamadı.")
            with col_sil:
                st.write("🗑️ **Hesap Sil**")
                del_b_id = st.number_input("Silinecek Banka ID:", min_value=1, step=1, key="del_b_id")
                if st.button("Hesabı Sil"):
                    conn, cursor = get_db()
                    cursor.execute("DELETE FROM bankalar WHERE id = ? AND user_id = ?", (del_b_id, current_user_id))
                    conn.commit()
                    conn.close()
                    st.success("Silindi!")
                    st.rerun()
        else:
            st.info("Kayıtlı banka hesabı yok.")

    # -------------------- 2. KREDİ KARTLARI --------------------
    with tabs[1]:
        st.subheader("Kredi Kartları Yönetimi")
        with st.form("card_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                c_name = st.text_input("Kart Adı", placeholder="Örn. Bonus Kart")
            with col2:
                c_limit = st.number_input("Toplam Limit (TL)", min_value=0.0, step=500.0, format="%.2f")
            with col3:
                c_avail = st.number_input("Kullanılabilir Limit (TL)", min_value=0.0, step=500.0, format="%.2f")
            if st.form_submit_button("Yeni Kart Ekle"):
                if not c_name:
                    st.warning("Kart adı girin.")
                elif c_avail > c_limit:
                    st.error("Kullanılabilir limit toplam limiti aşamaz.")
                else:
                    conn, cursor = get_db()
                    cursor.execute("INSERT INTO kartlar (user_id, ad, limit_tutar, kullanilabilir_tutar) VALUES (?, ?, ?, ?)", (current_user_id, c_name, c_limit, c_avail))
                    conn.commit()
                    conn.close()
                    st.success("Kart eklendi!")
                    st.rerun()

        if kartlar:
            card_data = [{"ID": k[0], "Kart Adı": k[1], "Limit": k[2], "Kullanılabilir": k[3], "Borç": max(0, k[2]-k[3])} for k in kartlar]
            st.dataframe(pd.DataFrame(card_data), use_container_width=True)

            st.markdown("---")
            col_c_d, col_c_s = st.columns(2)
            with col_c_d:
                st.write("✏️ **Kart Düzenle**")
                edit_c_id = st.number_input("Düzenlenecek Kart ID:", min_value=1, step=1, key="edit_c_id")
                new_c_name = st.text_input("Yeni Kart Adı", key="new_c_name")
                new_c_lim = st.number_input("Yeni Toplam Limit", min_value=0.0, step=500.0, format="%.2f", key="new_c_lim")
                new_c_ava = st.number_input("Yeni Kullanılabilir Limit", min_value=0.0, step=500.0, format="%.2f", key="new_c_ava")
                if st.button("Kartı Güncelle"):
                    conn, cursor = get_db()
                    cursor.execute("UPDATE kartlar SET ad = ?, limit_tutar = ?, kullanilabilir_tutar = ? WHERE id = ? AND user_id = ?", (new_c_name, new_c_lim, new_c_ava, edit_c_id, current_user_id))
                    if cursor.rowcount > 0:
                        conn.commit()
                        st.success("Güncellendi!")
                        conn.close()
                        st.rerun()
                    else:
                        conn.close()
                        st.error("ID bulunamadı.")
            with col_c_s:
                st.write("🗑️ **Kart Sil**")
                del_c_id = st.number_input("Silinecek Kart ID:", min_value=1, step=1, key="del_c_id")
                if st.button("Kartı Sil"):
                    conn, cursor = get_db()
                    cursor.execute("DELETE FROM kartlar WHERE id = ? AND user_id = ?", (del_c_id, current_user_id))
                    conn.commit()
                    conn.close()
                    st.rerun()
        else:
            st.info("Kayıtlı kart yok.")

    # -------------------- 3. ALACAKLAR --------------------
    with tabs[2]:
        st.subheader("Dışarıdaki Alacaklar Yönetimi")
        with st.form("rec_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                r_name = st.text_input("Kişi / Açıklama")
            with col2:
                r_amount = st.number_input("Kalan Alacak (TL)", min_value=0.0, step=100.0, format="%.2f")
            if st.form_submit_button("Alacak Ekle"):
                if not r_name:
                    st.warning("Açıklama girin.")
                else:
                    conn, cursor = get_db()
                    cursor.execute("INSERT INTO alacaklar (user_id, ad, tutar) VALUES (?, ?, ?)", (current_user_id, r_name, r_amount))
                    conn.commit()
                    conn.close()
                    st.success("Eklendi!")
                    st.rerun()

        if alacaklar:
            st.dataframe(pd.DataFrame(alacaklar, columns=["ID", "Açıklama", "Tutar"]), use_container_width=True)

            st.markdown("---")
            col_r_d, col_r_s = st.columns(2)
            with col_r_d:
                st.write("✏️ **Alacak Düzenle**")
                edit_r_id = st.number_input("Düzenlenecek Alacak ID:", min_value=1, step=1, key="edit_r_id")
                new_r_name = st.text_input("Yeni Açıklama", key="new_r_name")
                new_r_amt = st.number_input("Yeni Tutar", min_value=0.0, step=100.0, format="%.2f", key="new_r_amt")
                if st.button("Alacağı Güncelle"):
                    conn, cursor = get_db()
                    cursor.execute("UPDATE alacaklar SET ad = ?, tutar = ? WHERE id = ? AND user_id = ?", (new_r_name, new_r_amt, edit_r_id, current_user_id))
                    if cursor.rowcount > 0:
                        conn.commit()
                        st.success("Güncellendi!")
                        conn.close()
                        st.rerun()
                    else:
                        conn.close()
                        st.error("ID bulunamadı.")
            with col_r_s:
                st.write("🗑️ **Alacak Sil**")
                del_r_id = st.number_input("Silinecek Alacak ID:", min_value=1, step=1, key="del_r_id")
                if st.button("Alacağı Sil"):
                    conn, cursor = get_db()
                    cursor.execute("DELETE FROM alacaklar WHERE id = ? AND user_id = ?", (del_r_id, current_user_id))
                    conn.commit()
                    conn.close()
                    st.rerun()
        else:
            st.info("Kayıtlı alacak yok.")

    # -------------------- 4. DİĞER BORÇLAR --------------------
    with tabs[3]:
        st.subheader("Diğer Borçlar Yönetimi")
        with st.form("debt_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                d_name = st.text_input("Kişi / Açıklama")
            with col2:
                d_amount = st.number_input("Kalan Borç (TL)", min_value=0.0, step=100.0, format="%.2f")
            if st.form_submit_button("Borç Ekle"):
                if not d_name:
                    st.warning("Açıklama girin.")
                else:
                    conn, cursor = get_db()
                    cursor.execute("INSERT INTO borclar (user_id, ad, tutar) VALUES (?, ?, ?)", (current_user_id, d_name, d_amount))
                    conn.commit()
                    conn.close()
                    st.success("Eklendi!")
                    st.rerun()

        if borclar:
            st.dataframe(pd.DataFrame(borclar, columns=["ID", "Açıklama", "Tutar"]), use_container_width=True)

            st.markdown("---")
            col_d_d, col_d_s = st.columns(2)
            with col_d_d:
                st.write("✏️ **Borç Düzenle**")
                edit_d_id = st.number_input("Düzenlenecek Borç ID:", min_value=1, step=1, key="edit_d_id")
                new_d_name = st.text_input("Yeni Açıklama", key="new_d_name")
                new_d_amt = st.number_input("Yeni Tutar", min_value=0.0, step=100.0, format="%.2f", key="new_d_amt")
                if st.button("Borcu Güncelle"):
                    conn, cursor = get_db()
                    cursor.execute("UPDATE borclar SET ad = ?, tutar = ? WHERE id = ? AND user_id = ?", (new_d_name, new_d_amt, edit_d_id, current_user_id))
                    if cursor.rowcount > 0:
                        conn.commit()
                        st.success("Güncellendi!")
                        conn.close()
                        st.rerun()
                    else:
                        conn.close()
                        st.error("ID bulunamadı.")
            with col_d_s:
                st.write("🗑️ **Borç Sil**")
                del_d_id = st.number_input("Silinecek Borç ID:", min_value=1, step=1, key="del_d_id")
                if st.button("Borcu Sil"):
                    conn, cursor = get_db()
                    cursor.execute("DELETE FROM borclar WHERE id = ? AND user_id = ?", (del_d_id, current_user_id))
                    conn.commit()
                    conn.close()
                    st.rerun()
        else:
            st.info("Kayıtlı borç yok.")

    # -------------------- 5. YEDEKLEME --------------------
    with tabs[4]:
        st.subheader("Yedekleme ve Aktarım")
        user_backup = {
            "banks": [{"name": b[1], "amount": b[2]} for b in bankalar],
            "cards": [{"name": k[1], "limit": k[2], "available": k[3]} for k in kartlar],
            "receivables": [{"name": a[1], "amount": a[2]} for a in alacaklar],
            "debts": [{"name": d[1], "amount": d[2]} for d in borclar]
        }
        st.download_button("📥 Yedeği İndir (JSON)", data=json.dumps(user_backup, ensure_ascii=False, indent=2), file_name="yedek.json", mime="application/json")

    # -------------------- 6. YÖNETİCİ PANELİ --------------------
    if is_admin:
        with tabs[5]:
            st.subheader("👑 Yönetici Paneli")
            conn, cursor = get_db()
            cursor.execute("SELECT COUNT(*) FROM kullanicilar")
            u_count = cursor.fetchone()[0]
            cursor.execute("SELECT id, email FROM kullanicilar ORDER BY id ASC")
            all_users = cursor.fetchall()
            conn.close()

            st.metric("Toplam Kullanıcı", u_count)
            if all_users:
                st.dataframe(pd.DataFrame(all_users, columns=["ID", "E-Posta"]), use_container_width=True)
                del_u_id = st.number_input("Silinecek Kullanıcı ID:", min_value=1, step=1, key="del_u_id")
                if st.button("Kullanıcıyı Sil"):
                    if del_u_id == current_user_id:
                        st.error("Kendi hesabınızı silemezsiniz!")
                    else:
                        conn, cursor = get_db()
                        cursor.execute("DELETE FROM bankalar WHERE user_id = ?", (del_u_id,))
                        cursor.execute("DELETE FROM kartlar WHERE user_id = ?", (del_u_id,))
                        cursor.execute("DELETE FROM alacaklar WHERE user_id = ?", (del_u_id,))
                        cursor.execute("DELETE FROM borclar WHERE user_id = ?", (del_u_id,))
                        cursor.execute("DELETE FROM kullanicilar WHERE id = ?", (del_u_id,))
                        conn.commit()
                        conn.close()
                        st.success("Kullanıcı silindi!")
                        st.rerun()
