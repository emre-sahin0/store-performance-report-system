from flask import Flask, request, render_template, session
import pandas as pd
import os
from recommendations import generate_recommendations  # Öneri sistemini çağırıyoruz

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Flask session için gerekli
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Ürün kataloğunu oku (Bütün ürünler burada olacak)
KATALOG_DOSYA = os.path.join(os.getcwd(), "Kategoriler.csv")
if os.path.exists(KATALOG_DOSYA):
    katalog_df = pd.read_csv(KATALOG_DOSYA, encoding="utf-8", sep=";", low_memory=False)
    if "Ürün Tanım" in katalog_df.columns:
        urun_katalogu = set(katalog_df["Ürün Tanım"].dropna().str.strip().str.lower())  # Küçük harfe çevirerek kaydediyoruz
    else:
        urun_katalogu = set()
else:
    urun_katalogu = set()  # Eğer katalog yoksa boş bir set oluştur

def detect_and_extract_columns(file_path):
    """CSV dosyasındaki 'Malzeme Grubu' ve 'Net Satış Miktarı' sütunlarını otomatik bulur ve temizler."""
    df = pd.read_csv(file_path, encoding="utf-8", sep=";", low_memory=False, header=None)

    malzeme_sutun = None
    satis_sutun = None
    data_start_row = None  # Gerçek verilerin başladığı satır

    # "Malzeme Grubu" ve "Net Satış Miktarı" başlıklarını belirleme
    malzeme_keywords = ["malzeme grubu", "ürün grubu", "malzeme adı"]
    satis_keywords = ["net satış miktarı", "satış miktar", "toplam satış"]

    # İlk 50 satırı kontrol ederek sütun başlıklarını bul
    for i in range(50):
        row_values = df.iloc[i].astype(str).str.lower()  # Küçük harfe çevir
        for keyword in malzeme_keywords:
            if keyword in row_values.values:
                malzeme_sutun = row_values[row_values == keyword].index[0]
        for keyword in satis_keywords:
            if keyword in row_values.values:
                satis_sutun = row_values[row_values == keyword].index[0]

        # İkisini de farklı satırlarda bile bulduysak, satır numarasını belirle
        if malzeme_sutun is not None or satis_sutun is not None:
            data_start_row = i  # İlk bulunan satırdan itibaren okumaya başla

        if malzeme_sutun is not None and satis_sutun is not None:
            break  # İkisini de bulduğumuz için döngüyü durdur

    if malzeme_sutun is None or satis_sutun is None or data_start_row is None:
        raise ValueError("Malzeme Grubu veya Net Satış Miktarı sütunu bulunamadı!")

    # Verileri al ve temizle
    df_cleaned = df.iloc[data_start_row + 1:, [malzeme_sutun, satis_sutun]]
    df_cleaned.columns = ["Malzeme Grubu", "Net Satış Miktarı"]
    df_cleaned = df_cleaned.dropna()

    # Net Satış Miktarı sütununu sayıya çevir
    df_cleaned["Net Satış Miktarı"] = df_cleaned["Net Satış Miktarı"].astype(str) \
        .str.replace(".", "", regex=False).str.replace(",", ".", regex=False).astype(float)

    return df_cleaned

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    table_html = None
    filtered_table_html = None
    selected_filter = None
    recommendation_html = None
    eksik_urunler_html = None

    if request.method == 'GET':
        session.pop('data', None)

    if request.method == 'POST' and 'file' in request.files:
        file = request.files['file']
        if file:
            file_path = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(file_path)

            try:
                df_cleaned = detect_and_extract_columns(file_path)  # Otomatik sütun tespiti
                session['data'] = df_cleaned.to_dict(orient="records")
                table_html = df_cleaned.to_html(classes='table table-striped', index=False)

                # Öneri sistemini çağır
                recommendation_html = generate_recommendations(df_cleaned)

                # Eksik ürünleri kontrol et
                satilan_urunler = set(df_cleaned["Malzeme Grubu"].str.strip().str.lower())  # Temizleyip küçük harfe çevirelim
                eksik_urunler = urun_katalogu - satilan_urunler  # Katalogda olup satılmayan ürünler

                if eksik_urunler:
                    eksik_urunler_html = "<br>".join(sorted(eksik_urunler))  # Alfabetik sıraya koyarak listeleyelim

            except Exception as e:
                import traceback
                return f"Hata oluştu:<br><pre>{traceback.format_exc()}</pre>"

    return render_template('index.html', table=table_html, 
                           filtered_table=filtered_table_html, 
                           selected_filter=selected_filter, 
                           recommendations=recommendation_html, 
                           missing_products=eksik_urunler_html)

if __name__ == '__main__':
    app.run(debug=True)
