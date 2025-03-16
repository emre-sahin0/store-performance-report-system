import json
import os
import pandas as pd
import sys
import psutil
from flask import Flask, request, render_template, redirect, url_for, session
from recommendations import generate_recommendations

app = Flask(__name__)
app.secret_key = "supersecretkey"
UPLOAD_FOLDER = 'uploads'
RULES_FILE = "rules.json"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 📌 Eğer PyInstaller ile çalışıyorsak, doğru dizini bul
if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
else:
    application_path = os.getcwd()

KATALOG_DOSYA = "Kategoriler.csv"  # Hep dışarıdaki güncel dosyayı kullan



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
    with open(RULES_FILE, "r", encoding="utf-8") as file:
        return json.load(file)

def save_rules(rules):
    with open(RULES_FILE, "w", encoding="utf-8") as file:
        json.dump(rules, file, indent=4, ensure_ascii=False)

def detect_and_extract_columns(file_path):
    """CSV dosyasındaki 'Malzeme Grubu' ve 'Net Satış Miktarı' sütunlarını otomatik bulur ve temizler."""
    df = pd.read_csv(file_path, encoding="utf-8", sep=";", low_memory=False, header=None)

    malzeme_sutun = None
    satis_sutun = None
    data_start_row = None

    malzeme_keywords = ["malzeme grubu", "ürün grubu", "malzeme adı"]
    satis_keywords = ["net satış miktarı", "satış miktar", "toplam satış"]

    for i in range(50):  # İlk 50 satırı tarayarak başlığı bul
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
    
    # 🔹 Ondalıklı sayıları düzelt (önce virgülü noktaya çevir, sonra sayıya dönüştür)
    df_cleaned["Net Satış Miktarı"] = df_cleaned["Net Satış Miktarı"].astype(str).str.replace(",", ".", regex=False)
    df_cleaned["Net Satış Miktarı"] = pd.to_numeric(df_cleaned["Net Satış Miktarı"], errors='coerce')
    
    return df_cleaned

def generate_recommendations(df):
    """Kullanıcının belirlediği kriterlere göre gruplandırılmış satışları analiz eder."""
    rules = load_rules()
    recommendations = []

    # 🔹 Aynı ürün isimlerini olduğu gibi tutarak gruplandır ve toplam satışları hesapla
    grouped_df = df.groupby("Malzeme Grubu", as_index=False).sum()
    print("✅ Toplam Satışlar:")
    print(grouped_df)

    for rule in rules:
        keyword = rule["keyword"].strip()
        threshold = rule["threshold"]
        message = rule["message"]
        
        # 🔹 str.contains() regex olmadan filtreleme yap
        filtered_df = grouped_df[grouped_df["Malzeme Grubu"].str.contains(keyword, case=False, na=False, regex=False)]
        total_sales = filtered_df["Net Satış Miktarı"].sum()
        print(f"🔍 '{keyword}' için toplam satış: {total_sales}")
        
        if total_sales > 0 and total_sales < threshold:
            recommendations.append(f"🔹 '{keyword}' içeren ürünlerin toplam satışı ({total_sales}) eşik değerinin altında ({threshold}). {message}")
    
    return "<br>".join(recommendations) if recommendations else "✅ Tüm ürünler yeterince satılmış görünüyor!"

@app.route("/", methods=["GET", "POST"])
def upload_file():
    recommendations_html = None
    table_html = None
    missing_products_html = None

    if request.method == "POST" and 'file' in request.files:
        file = request.files['file']
        if file:
            file_path = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(file_path)
            try:
                df_cleaned = detect_and_extract_columns(file_path)
                session['data'] = df_cleaned.to_dict(orient="records")
                recommendations_html = generate_recommendations(df_cleaned)
                table_html = df_cleaned.to_html(classes='table table-striped', index=False)

                if urun_katalogu:
                     satilan_urunler = set(df_cleaned["Malzeme Grubu"].astype(str).str.strip().str.lower())
                     eksik_urunler = urun_katalogu - satilan_urunler
                     missing_products_html = "<br>".join(sorted(eksik_urunler)) if eksik_urunler else "✅ Tüm ürünler satılmış!"
                else:
                     missing_products_html = "⚠️ Ürün kataloğu yüklenmediği için eksik ürünler hesaplanamıyor."
            except Exception as e:
                return f"Hata oluştu:<br><pre>{str(e)}</pre>"
    return render_template("index.html", recommendations=recommendations_html, table=table_html, missing_products=missing_products_html)

@app.route("/admin", methods=["GET", "POST"])
def admin_panel():
    rules = load_rules()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            keyword = request.form.get("keyword").strip()
            threshold = int(request.form.get("threshold"))
            message = request.form.get("message")
            rules.append({"keyword": keyword, "threshold": threshold, "message": message})
            save_rules(rules)
        elif action == "delete":
            index = int(request.form.get("index"))
            if 0 <= index < len(rules):
                del rules[index]
                save_rules(rules)
        return redirect(url_for("admin_panel"))
    return render_template("admin.html", rules=rules)

if __name__ == "__main__":
    app.run(debug=True)