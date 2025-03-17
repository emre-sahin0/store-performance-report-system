import json
import os
import io
import base64
import pandas as pd
import sys
import psutil
import matplotlib.pyplot as plt
from flask import Flask, request, render_template, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "supersecretkey"
UPLOAD_FOLDER = 'uploads'
RULES_FILE = "rules.json"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

KATALOG_DOSYA = "Kategoriler.csv"

# 📌 Ürün kataloğunu oku veya boş set oluştur
if os.path.exists(KATALOG_DOSYA):
    katalog_df = pd.read_csv(KATALOG_DOSYA, encoding="utf-8", sep=";", low_memory=False)
    if "Ürün Tanım" in katalog_df.columns:
        urun_katalogu = set(katalog_df["Ürün Tanım"].astype(str).str.strip())
    else:
        urun_katalogu = set()
else:
    urun_katalogu = set()

def load_rules():
    if not os.path.exists(RULES_FILE):
        with open(RULES_FILE, "w", encoding="utf-8") as file:
            json.dump([], file)
    with open(RULES_FILE, "r", encoding="utf-8") as file:
        return json.load(file)

def detect_and_extract_columns(file_path):
    df = pd.read_csv(file_path, encoding="utf-8", sep=";", low_memory=False, header=None)
    malzeme_sutun = satis_sutun = data_start_row = None

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

    # 🔹 HATA DÜZELTME: Sayıları düzgün şekilde temizle ve çevir
    df_cleaned["Net Satış Miktarı"] = df_cleaned["Net Satış Miktarı"].astype(str) \
    .str.replace(r"[^\d,]", "", regex=True) \
    .str.replace(".", "", regex=False) \
    .str.replace(",", ".", regex=False)

    df_cleaned["Net Satış Miktarı"] = pd.to_numeric(df_cleaned["Net Satış Miktarı"], errors='coerce')  
 

    return df_cleaned

def generate_recommendations(df):
    rules = load_rules()
    recommendations = []

    grouped_df = df.groupby("Malzeme Grubu", as_index=False).sum()

    for rule in rules:
        keyword = rule["keyword"].strip()
        threshold = rule["threshold"]
        message = rule["message"]
        
        filtered_df = grouped_df[grouped_df["Malzeme Grubu"].str.contains(keyword, case=False, na=False, regex=False)]
        total_sales = filtered_df["Net Satış Miktarı"].sum()
        
        if total_sales > 0 and total_sales < threshold:
            recommendations.append(f"🔹 '{keyword}' içeren ürünlerin toplam satışı ({total_sales}) eşik değerinin altında ({threshold}). {message}")
    
    return "<br>".join(recommendations) if recommendations else "✅ Tüm ürünler yeterince satılmış görünüyor!"


# 📌 Satış oranlarını ve kategorilere göre satışları içeren Pie Chart oluşturma
def generate_pie_chart(satilan_urunler, satilmayan_urunler, df):
    fig, axs = plt.subplots(1, 3, figsize=(22, 8))  # Grafikleri daha büyük yaptık

    # ✅ Genel Satış Oranları Pie Chart
    genel_labels = ['Satılan Ürünler', 'Satılmayan Ürünler']
    genel_sizes = [len(satilan_urunler), len(satilmayan_urunler)]
    genel_colors = ['#ff6347', '#4caf50']
    explode = (0, 0.1) 

    axs[0].pie(genel_sizes, labels=genel_labels, autopct='%1.1f%%', startangle=140, 
               colors=genel_colors, explode=explode, shadow=True, textprops={'fontsize': 14})
    axs[0].set_title("📊 Genel Satış Oranları", fontsize=18, fontweight='bold')

    # ✅ Satılan Ürünlerin Kategori Dağılımı Pie Chart
    categories = ["AdaHome", "AdaPanel", "AdaWall"]
    category_sales = {cat: df[df["Malzeme Grubu"].str.contains(cat, case=False, na=False)]["Net Satış Miktarı"].sum() for cat in categories}

    axs[1].pie(list(category_sales.values()), labels=list(category_sales.keys()), autopct='%1.1f%%', 
               startangle=140, colors=['#ffcc00', '#66b3ff', '#99ff99'], textprops={'fontsize': 14})
    axs[1].set_title("📈 Satılan Ürünlerin Kategori Dağılımı", fontsize=18, fontweight='bold')

    # ✅ Satılmayan Ürünlerin Kategori Dağılımı Pie Chart
    satilmayan_category_counts = {cat: sum(1 for urun in satilmayan_urunler if cat in urun) for cat in categories}

    # Eğer tüm kategoriler 0 ise, farklı bir mesaj göster
    if sum(satilmayan_category_counts.values()) == 0:
        axs[2].text(0.5, 0.5, "✅ Tüm Ürünler Satılmış", fontsize=16, ha='center', va='center', transform=axs[2].transAxes)
        axs[2].set_xticks([])
        axs[2].set_yticks([])
        axs[2].set_title("📉 Satılmayan Ürünler Yok", fontsize=18, fontweight='bold')
    else:
        axs[2].pie(
            list(satilmayan_category_counts.values()), 
            labels=[label if value > 0 else "N/A" for label, value in satilmayan_category_counts.items()],
            autopct=lambda p: f'{p:.1f}%' if p > 0 else '',
            startangle=140, colors=['#ffcc00', '#66b3ff', '#99ff99'], textprops={'fontsize': 14}
        )
        axs[2].set_title("📉 Satılmayan Ürünlerin Kategori Dağılımı", fontsize=18, fontweight='bold')

    # ✅ Grafik kaydet ve encode et
    plt.tight_layout()  # Grafiklerin birbirine çok yakın olmamasını sağlar
    img = io.BytesIO()
    plt.savefig(img, format='png', dpi=100)  # DPI artırıldı
    img.seek(0)
    pie_chart_url = base64.b64encode(img.getvalue()).decode('utf8')
    plt.close(fig)

    return pie_chart_url

@app.route("/", methods=["GET", "POST"])
def upload_file():
    recommendations_html = None
    table_html = None
    missing_products_html = None
    pie_chart_url = None

    if request.method == "POST" and 'file' in request.files:
        file = request.files['file']
        if file:
            file_path = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(file_path)
            try:
                df_cleaned = detect_and_extract_columns(file_path)
                session['data'] = df_cleaned.to_dict(orient="records")
                table_html = df_cleaned.to_html(classes='table table-striped', index=False)

                satilan_urunler = set(df_cleaned["Malzeme Grubu"].astype(str).str.strip())
                satilmayan_urunler = urun_katalogu - satilan_urunler

                # **ÖNERİLERİN TEKRAR EKLENMESİ**
                recommendations_html = generate_recommendations(df_cleaned)

                pie_chart_url = generate_pie_chart(satilan_urunler, satilmayan_urunler, df_cleaned)

                if urun_katalogu:
                    missing_products_html = "<br>".join(sorted(satilmayan_urunler)) if satilmayan_urunler else "✅ Tüm ürünler satılmış!"
                else:
                    missing_products_html = "⚠️ Ürün kataloğu yüklenmediği için eksik ürünler hesaplanamıyor."

            except Exception as e:
                return f"Hata oluştu:<br><pre>{str(e)}</pre>"
    
    return render_template("index.html", table=table_html, recommendations=recommendations_html, missing_products=missing_products_html, pie_chart_url=pie_chart_url)


if __name__ == "__main__":
    app.run(debug=True)
