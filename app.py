import streamlit as st
import sqlite3
from datetime import date
import os

DB_NAME = "aidat.db"
YONETICI_SIFRE = "1234"
UPLOAD_DIR = "dekontlar"

os.makedirs(UPLOAD_DIR, exist_ok=True)

def connect_db():
    return sqlite3.connect(DB_NAME)

def create_tables():
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        daire_no TEXT,
        ay TEXT,
        tarih TEXT,
        miktar REAL,
        durum TEXT,
        dekont_yolu TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    cursor.execute("PRAGMA table_info(payments)")
    columns = [column[1] for column in cursor.fetchall()]

    if "dekont_yolu" not in columns:
        cursor.execute("ALTER TABLE payments ADD COLUMN dekont_yolu TEXT")

    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('aidat_tutari', '500')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('daire_sayisi', '20')")

    conn.commit()
    conn.close()

def get_setting(key, default_value):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else default_value

def update_setting(key, value):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO settings (key, value)
    VALUES (?, ?)
    ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (key, str(value)))
    conn.commit()
    conn.close()

def save_payment(daire_no, ay, tarih, miktar, dekont_yolu):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO payments (daire_no, ay, tarih, miktar, durum, dekont_yolu)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (daire_no, ay, str(tarih), miktar, "Beklemede", dekont_yolu))
    conn.commit()
    conn.close()

def get_payments():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, daire_no, ay, tarih, miktar, durum, dekont_yolu
    FROM payments
    ORDER BY id DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows

def approve_payment(payment_id):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE payments
    SET durum = ?
    WHERE id = ?
    """, ("Onaylandı", payment_id))
    conn.commit()
    conn.close()

def delete_payment(payment_id):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("SELECT dekont_yolu FROM payments WHERE id = ?", (payment_id,))
    result = cursor.fetchone()

    if result:
        dekont_yolu = result[0]
        if dekont_yolu and os.path.exists(dekont_yolu):
            os.remove(dekont_yolu)

    cursor.execute("DELETE FROM payments WHERE id = ?", (payment_id,))
    conn.commit()
    conn.close()

def save_receipt_file(dekont, daire_no, ay):
    safe_ay = ay.replace(" ", "_")
    file_name = f"daire_{daire_no}_{safe_ay}_{dekont.name}"
    file_path = os.path.join(UPLOAD_DIR, file_name)

    with open(file_path, "wb") as f:
        f.write(dekont.getbuffer())

    return file_path

def create_whatsapp_summary(kayitlar, daireler, secilen_ay, aidat_tutari):
    odedi = []
    bekliyor = []
    odemedi = []

    for daire in daireler:
        durum = "Yok"

        for kayit in kayitlar:
            _, daire_no, kayit_ay, tarih, miktar, odeme_durumu, dekont_yolu = kayit

            if daire_no == daire and kayit_ay == secilen_ay:
                if odeme_durumu == "Onaylandı":
                    durum = "Onaylandı"
                    break
                elif odeme_durumu == "Beklemede":
                    durum = "Beklemede"

        if durum == "Onaylandı":
            odedi.append(daire)
        elif durum == "Beklemede":
            bekliyor.append(daire)
        else:
            odemedi.append(daire)

    mesaj = f"📌 {secilen_ay.upper()} AİDAT DURUMU\n\n"
    mesaj += f"Aidat Tutarı: {aidat_tutari:.2f} TL\n\n"

    mesaj += "✅ ÖDEYEN DAİRELER:\n"
    if odedi:
        for daire in odedi:
            mesaj += f"- Daire {daire}\n"
    else:
        mesaj += "- Yok\n"

    mesaj += "\n⏳ ONAY BEKLEYENLER:\n"
    if bekliyor:
        for daire in bekliyor:
            mesaj += f"- Daire {daire}\n"
    else:
        mesaj += "- Yok\n"

    mesaj += "\n❌ ÖDEME GÖRÜNMEYEN DAİRELER:\n"
    if odemedi:
        for daire in odemedi:
            mesaj += f"- Daire {daire}\n"
    else:
        mesaj += "- Yok\n"

    mesaj += "\nNot: Onay bekleyen ödemeler, yönetici dekont kontrolünden sonra kesinleşecektir."

    return mesaj

create_tables()

aidat_tutari = float(get_setting("aidat_tutari", "500"))
daire_sayisi = int(get_setting("daire_sayisi", "20"))

st.set_page_config(
    page_title="Apartman Aidat Takip Sistemi",
    layout="wide"
)

st.title("🏢 Apartman Aidat Takip Sistemi")

daireler = [str(i) for i in range(1, daire_sayisi + 1)]

aylar = [
    "Ocak 2026", "Şubat 2026", "Mart 2026", "Nisan 2026",
    "Mayıs 2026", "Haziran 2026", "Temmuz 2026", "Ağustos 2026",
    "Eylül 2026", "Ekim 2026", "Kasım 2026", "Aralık 2026"
]

menu = st.sidebar.radio(
    "Menü",
    ["Ödeme Bildir", "Borç / Ödeme Sorgula", "Yönetici Paneli"]
)

if menu == "Ödeme Bildir":
    st.header("Aidat Ödeme Bildirimi")
    st.info(f"Güncel aidat tutarı: {aidat_tutari:.2f} TL")

    daire_no = st.selectbox("Daire No Seçiniz", daireler)
    ay = st.selectbox("Aidat Ayı", aylar)
    tarih = st.date_input("Ödeme Tarihi", date.today())
    miktar = st.number_input("Ödenen Tutar (TL)", min_value=0.0, step=50.0)
    dekont = st.file_uploader("Dekont Yükle", type=["pdf", "jpg", "jpeg", "png"])

    if st.button("Ödemeyi Bildir"):
        if miktar <= 0:
            st.error("Lütfen geçerli bir tutar giriniz.")
        elif dekont is None:
            st.error("Lütfen dekont yükleyiniz.")
        else:
            dekont_yolu = save_receipt_file(dekont, daire_no, ay)
            save_payment(daire_no, ay, tarih, miktar, dekont_yolu)

            st.success(f"{daire_no} numaralı dairenin {ay} aidat bildirimi kaydedildi.")
            st.info("Ödeme, yönetici onayından sonra ödendi olarak görünecektir.")

elif menu == "Borç / Ödeme Sorgula":
    st.header("Borç / Ödeme Sorgula")

    secilen_daire = st.selectbox("Daire No Seçiniz", daireler)

    if st.button("Sorgula"):
        kayitlar = get_payments()

        toplam_borc = 0
        toplam_odeme = 0

        st.subheader(f"Daire {secilen_daire} Ödeme Durumu")

        for ay in aylar:
            onayli_odeme_var = False
            bekleyen_odeme_var = False
            odenen_miktar = 0

            for kayit in kayitlar:
                _, daire_no, kayit_ay, tarih, miktar, durum, dekont_yolu = kayit

                if daire_no == secilen_daire and kayit_ay == ay:
                    if durum == "Onaylandı":
                        onayli_odeme_var = True
                        odenen_miktar += miktar
                    elif durum == "Beklemede":
                        bekleyen_odeme_var = True

            if onayli_odeme_var:
                st.success(f"{ay}: ✅ Ödendi - {odenen_miktar} TL")
                toplam_odeme += odenen_miktar
            elif bekleyen_odeme_var:
                st.warning(f"{ay}: ⏳ Ödeme bildirimi var, yönetici onayı bekliyor")
                toplam_borc += aidat_tutari
            else:
                st.error(f"{ay}: ❌ Ödenmedi")
                toplam_borc += aidat_tutari

        st.divider()
        st.subheader(f"Toplam Onaylı Ödeme: {toplam_odeme} TL")
        st.subheader(f"Tahmini Açık Borç: {toplam_borc} TL")

elif menu == "Yönetici Paneli":
    st.header("Yönetici Paneli")

    sifre = st.text_input("Yönetici Şifresi", type="password")

    if sifre == YONETICI_SIFRE:
        st.success("Yönetici girişi başarılı.")

        st.subheader("Sistem Ayarları")

        yeni_aidat_tutari = st.number_input(
            "Aidat Tutarı (TL)",
            min_value=0.0,
            value=aidat_tutari,
            step=50.0
        )

        yeni_daire_sayisi = st.number_input(
            "Daire Sayısı",
            min_value=1,
            value=daire_sayisi,
            step=1
        )

        if st.button("Ayarları Kaydet"):
            update_setting("aidat_tutari", yeni_aidat_tutari)
            update_setting("daire_sayisi", int(yeni_daire_sayisi))
            st.success("Ayarlar kaydedildi.")
            st.rerun()

        st.divider()

        kayitlar = get_payments()

        if kayitlar:
            st.subheader("Tüm Ödeme Bildirimleri")
            st.table(kayitlar)

            st.divider()
            st.subheader("Aylık Genel Apartman Durumu")

            secilen_ay_genel = st.selectbox(
                "Genel durum için ay seçiniz",
                aylar,
                key="genel_durum_ayi"
            )

            for daire in daireler:
                durum_text = "❌ Ödemedi"

                for kayit in kayitlar:
                    _, daire_no, kayit_ay, tarih, miktar, odeme_durumu, dekont_yolu = kayit

                    if daire_no == daire and kayit_ay == secilen_ay_genel:
                        if odeme_durumu == "Onaylandı":
                            durum_text = "✅ Ödedi"
                        elif odeme_durumu == "Beklemede":
                            durum_text = "⏳ Onay Bekliyor"

                if durum_text == "✅ Ödedi":
                    st.success(f"Daire {daire}: {durum_text}")
                elif durum_text == "⏳ Onay Bekliyor":
                    st.warning(f"Daire {daire}: {durum_text}")
                else:
                    st.error(f"Daire {daire}: {durum_text}")

            st.divider()
            st.subheader("WhatsApp Grup Özeti")

            secilen_ay_whatsapp = st.selectbox(
                "WhatsApp özeti için ay seçiniz",
                aylar,
                key="whatsapp_ozet_ayi"
            )

            if st.button("WhatsApp Özeti Oluştur"):
                whatsapp_mesaji = create_whatsapp_summary(
                    kayitlar,
                    daireler,
                    secilen_ay_whatsapp,
                    aidat_tutari
                )

                st.text_area(
                    "Aşağıdaki metni kopyalayıp WhatsApp grubuna gönderebilirsiniz:",
                    whatsapp_mesaji,
                    height=350
                )

            st.divider()
            st.subheader("Bekleyen Ödemeleri Onayla")

            bekleyenler = [k for k in kayitlar if k[5] == "Beklemede"]

            if bekleyenler:
                for kayit in bekleyenler:
                    payment_id, daire_no, ay, tarih, miktar, durum, dekont_yolu = kayit

                    col1, col2 = st.columns([4, 1])

                    with col1:
                        st.write(
                            f"ID: {payment_id} | Daire: {daire_no} | Ay: {ay} | "
                            f"Tarih: {tarih} | Tutar: {miktar} TL | Durum: {durum}"
                        )

                        st.write(f"Dekont yolu: {dekont_yolu}")

                        if dekont_yolu and os.path.exists(dekont_yolu):
                            dosya_uzantisi = dekont_yolu.lower()

                            if dosya_uzantisi.endswith((".jpg", ".jpeg", ".png")):
                                st.image(dekont_yolu, caption="Yüklenen Dekont", width=300)

                            elif dosya_uzantisi.endswith(".pdf"):
                                with open(dekont_yolu, "rb") as pdf_file:
                                    st.download_button(
                                        label="PDF Dekontu İndir",
                                        data=pdf_file,
                                        file_name=os.path.basename(dekont_yolu),
                                        mime="application/pdf",
                                        key=f"indir_{payment_id}"
                                    )
                        else:
                            st.warning("Dekont dosyası bulunamadı.")

                    with col2:
                        if st.button("Onayla", key=f"onayla_{payment_id}"):
                            approve_payment(payment_id)
                            st.success(f"{payment_id} numaralı ödeme onaylandı.")
                            st.rerun()
            else:
                st.info("Bekleyen ödeme bulunmamaktadır.")

            st.divider()
            st.subheader("Kayıt Silme")

            silinecek_id = st.number_input(
                "Silinecek kayıt ID numarasını giriniz",
                min_value=1,
                step=1
            )

            silme_onayi = st.checkbox("Bu kaydı silmek istediğimi onaylıyorum.")

            if st.button("Kaydı Sil"):
                if silme_onayi:
                    delete_payment(silinecek_id)
                    st.success(f"{silinecek_id} ID numaralı kayıt silindi.")
                    st.rerun()
                else:
                    st.warning("Silme işlemi için onay kutusunu işaretleyiniz.")

        else:
            st.info("Henüz kayıt bulunmamaktadır.")

    elif sifre:
        st.error("Yönetici şifresi hatalı.")