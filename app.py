from flask import Flask, request, render_template, session
import pandas as pd
import os
import sys
import signal
import psutil  # Çalışan süreçleri yönetmek için
from recommendations import generate_recommendations  # 📌 Öneri sistemini çağır

app = Flask(__name__)
app.secret_key = "supersecretkey"
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 📌 Önceki Çalışan `app.exe` Süreçlerini Kapat
def kill_existing_process():
    current_pid = os.getpid()
    for process in psutil.process_iter(attrs=['pid', 'name']):
        try:
            if "app.exe" in process.info['name'].lower() and process.info['pid'] != current_pid:
                print(f"⚠️ Önceki çalışan `app.exe` süreci kapatılıyor: PID {process.info['pid']}")
                proc = psutil.Process(process.info['pid'])
                proc.terminate()  # Süreci sonlandır
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

kill_existing_process()

# 📌 Eğer PyInstaller ile çalışıyorsak, doğru dizini bul
if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
else:
    application_path = os.getcwd()

KATALOG_DOSYA = os.path.join(application_path, "Kategoriler.csv")

# 📌 Kategoriler.csv Dosyasının Gerçekten Yüklendiğini Kontrol Et
print(f"📂 Kategori dosyası yolu: {KATALOG_DOSYA}")

if not os.path.exists(KATALOG_DOSYA):
    print("⚠️ Kategoriler.csv dosyası BULUNAMADI!")
else:
    print("✅ Kategoriler.csv dosyası bulundu!")

# 📌 Ürün kataloğunu oku
if os.path.exists(KATALOG_DOSYA):
    katalog_df = pd.read_csv(KATALOG_DOSYA, encoding="utf-8", sep=";", low_memory=False)
    if "Ürün Tanım" in katalog_df.columns:
        urun_katalogu = set(katalog_df["Ürün Tanım"].astype(str).str.strip().str.lower())  
    else:
        urun_katalogu = set()
else:
    urun_katalogu = set()

def detect_and_extract_columns(file_path):
    """CSV dosyasındaki 'Malzeme Grubu' ve 'Net Satış Miktarı' sütunlarını otomatik bulur ve temizler."""
    df = pd.read_csv(file_path, encoding="utf-8", sep=";", low_memory=False, header=None)

    malzeme_sutun = None
    satis_sutun = None
    data_start_row = None

    malzeme_keywords = ["malzeme grubu", "ürün grubu", "malzeme adı"]
    satis_keywords = ["net satış miktarı", "satış miktar", "toplam satış"]

    for i in range(50):
        row_values = df.iloc[i].astype(str).str.lower()
        for keyword in malzeme_keywords:
            if keyword in row_values.values:
                malzeme_sutun = row_values[row_values == keyword].index[0]
        for keyword in satis_keywords:
            if keyword in row_values.values:
                satis_sutun = row_values[row_values == keyword].index[0]

        if malzeme_sutun is not None and satis_sutun is not None:
            data_start_row = i
            break

    if malzeme_sutun is None or satis_sutun is None or data_start_row is None:
        raise ValueError("Malzeme Grubu veya Net Satış Miktarı sütunu bulunamadı!")

    df_cleaned = df.iloc[data_start_row + 1:, [malzeme_sutun, satis_sutun]]
    df_cleaned.columns = ["Malzeme Grubu", "Net Satış Miktarı"]
    df_cleaned = df_cleaned.dropna()
    df_cleaned["Net Satış Miktarı"] = df_cleaned["Net Satış Miktarı"].astype(str) \
        .str.replace(".", "", regex=False).str.replace(",", ".", regex=False).astype(float)

    return df_cleaned

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    table_html = None
    filtered_table_html = None
    selected_filter = None
    eksik_urunler_html = None
    recommendations_html = None  

    if request.method == 'GET':
        session.pop('data', None)
        session.pop('recommendations', None)  # 📌 Önerileri temizle
        session.pop('missing_products', None)  # 📌 Eksik ürünleri temizle

    if request.method == 'POST' and 'file' in request.files:
        file = request.files['file']
        if file:
            file_path = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(file_path)

            try:
                df_cleaned = detect_and_extract_columns(file_path)
                session['data'] = df_cleaned.to_dict(orient="records")  # 📌 Verileri session'a kaydediyoruz!

                table_html = df_cleaned.to_html(classes='table table-striped', index=False)

                # 📌 Eksik ürünleri hesapla ve session içine kaydet
                satilan_urunler = set(df_cleaned["Malzeme Grubu"].astype(str).str.strip().str.lower())
                eksik_urunler = urun_katalogu - satilan_urunler
                if eksik_urunler:
                    eksik_urunler_html = "<br>".join(sorted(eksik_urunler))
                session['missing_products'] = eksik_urunler_html  # 📌 Eksik ürünleri session içinde tut

                # 📌 ÖNERİLERİ OLUŞTUR ve session içinde sakla
                recommendations_html = generate_recommendations(df_cleaned)
                session['recommendations'] = recommendations_html  # 📌 Önerileri de session içinde tut

            except Exception as e:
                import traceback
                hata_mesaji = traceback.format_exc()
                print("⚠️ Hata oluştu:", hata_mesaji)
                with open("log.txt", "a") as log:
                    log.write("\n⚠️ Hata oluştu:\n" + hata_mesaji + "\n")
                return f"Hata oluştu:<br><pre>{hata_mesaji}</pre>"

    # 📌 Eğer filtreleme butonuna basılmışsa ve veri zaten yüklenmişse
    elif request.method == 'POST' and 'filter' in request.form:
        selected_filter = request.form.get("filter")
        if 'data' in session:
            df_cleaned = pd.DataFrame(session['data'])  # 📌 Session'dan veriyi geri al!
            table_html = df_cleaned.to_html(classes='table table-striped', index=False)

            # 📌 Seçili filtreye göre verileri süz
            filtered_df = df_cleaned[df_cleaned["Malzeme Grubu"].str.contains(selected_filter, case=False, na=False)]
            filtered_table_html = filtered_df.to_html(classes='table table-bordered', index=False)

            # 📌 Eksik ürünleri ve önerileri session'dan geri yükle
            eksik_urunler_html = session.get('missing_products', None)
            recommendations_html = session.get('recommendations', None)

    return render_template('index.html', 
                           table=table_html, 
                           filtered_table=filtered_table_html, 
                           selected_filter=selected_filter, 
                           missing_products=eksik_urunler_html,
                           recommendations=recommendations_html)  

if __name__ == '__main__':
    app.run(debug=True)
