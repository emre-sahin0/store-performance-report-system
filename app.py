import json
import os
import io
import base64
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # GUI backend hatalarını önlemek için
import sys
import psutil
import matplotlib.pyplot as plt
from flask import Flask, request, render_template, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "supersecretkey"
UPLOAD_FOLDER = 'uploads'
RULES_FILE = "rules.json"
MISSING_RULES_FILE = "missing_rules.json"  # Satılmayan ürünler için öneri dosyası
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

KATALOG_DOSYA = "Kategoriler.csv"

#  Ürün kataloğunu oku veya boş set oluştur
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

def save_rules(rules):
    with open(RULES_FILE, "w", encoding="utf-8") as file:
        json.dump(rules, file, indent=4, ensure_ascii=False)

def load_missing_rules():
    if not os.path.exists(MISSING_RULES_FILE):
        with open(MISSING_RULES_FILE, "w", encoding="utf-8") as file:
            json.dump([], file)
    with open(MISSING_RULES_FILE, "r", encoding="utf-8") as file:
        return json.load(file)

def save_missing_rules(missing_rules):
    with open(MISSING_RULES_FILE, "w", encoding="utf-8") as file:
        json.dump(missing_rules, file, indent=4, ensure_ascii=False)

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
            recommendations.append(
                f"🔹 <b>'{keyword}'</b> içeren ürünlerin toplam satışı <b>({total_sales})</b>  Eşik değerimizin <b>({threshold})</b> altında. Önerimiz;. {message}"
            )
    
    return "<br>".join(recommendations) if recommendations else "✅ Tüm ürünler yeterince satılmış görünüyor!"


def generate_missing_recommendations(satilmayan_urunler):
    missing_rules = load_missing_rules()
    recommendations = []

    for rule in missing_rules:
        keyword = rule["keyword"].strip()
        message = rule["message"]

        if any(keyword.lower() in urun.lower() for urun in satilmayan_urunler):
            recommendations.append(f"🔹 '{keyword}' ile ilgili öneri: {message}")

    return "<br>".join(recommendations) if recommendations else "✅ Satılmayan ürünler için özel bir öneri bulunmamaktadır."


def generate_pie_charts(satilan_urunler, satilmayan_urunler, df):
    categories = ["AdaHome", "AdaPanel", "AdaWall"]
    colors = ['#ffcc00', '#66b3ff', '#99ff99']

    chart_buffers = []

    # 1️⃣ Toplam Ürün Çeşidi Satış Yüzdesi
    fig1, ax1 = plt.subplots()
    genel_sizes = [len(satilan_urunler), len(satilmayan_urunler)]
    ax1.pie(genel_sizes, labels=['Satılan Ürünler', 'Satılmayan Ürünler'], autopct='%1.1f%%', startangle=140,
            colors=['#ff6347', '#4caf50'], explode=(0, 0.1), shadow=True, textprops={'fontsize': 12})
    ax1.set_title("📊 Toplam Ürün Çeşidinin Satış Yüzdesi", fontsize=15, fontweight='bold')
    buf1 = io.BytesIO()
    plt.savefig(buf1, format='png', dpi=200)
    buf1.seek(0)
    chart_buffers.append(base64.b64encode(buf1.getvalue()).decode('utf8'))
    plt.close(fig1)

    # 2️⃣ Satılan Ürünlerin Kategori Dağılımı
    fig2, ax2 = plt.subplots()
    category_sales = {cat: df[df["Malzeme Grubu"].str.contains(cat, case=False, na=False)]["Net Satış Miktarı"].sum() for cat in categories}
    total_sales = sum(category_sales.values())
    ax2.pie(list(category_sales.values()), labels=list(category_sales.keys()), autopct='%1.1f%%',
            startangle=140, colors=colors, textprops={'fontsize': 13})
    ax2.set_title("📈 Satılan Ürünlerin Kategori Dağılımı", fontsize=15, fontweight='bold')
    buf2 = io.BytesIO()
    plt.savefig(buf2, format='png', dpi=200)
    buf2.seek(0)
    chart_buffers.append(base64.b64encode(buf2.getvalue()).decode('utf8'))
    plt.close(fig2)

    # 3️⃣ Satılmayan Ürünlerin Kategori Dağılımı
    fig3, ax3 = plt.subplots()
    satilmayan_category_counts = {cat: sum(1 for urun in satilmayan_urunler if cat in urun) for cat in categories}
    ax3.pie(list(satilmayan_category_counts.values()), labels=list(satilmayan_category_counts.keys()),
            autopct='%1.1f%%', startangle=140, colors=colors, textprops={'fontsize': 13})
    ax3.set_title("📉 Satılmayan Ürünlerin Kategori Dağılımı", fontsize=15, fontweight='bold')
    buf3 = io.BytesIO()
    plt.savefig(buf3, format='png', dpi=200)
    buf3.seek(0)
    chart_buffers.append(base64.b64encode(buf3.getvalue()).decode('utf8'))
    plt.close(fig3)

    return chart_buffers

def generate_filtered_chart(data_dict, selected_categories, title, label_suffix):
    fig, ax = plt.subplots(figsize=(2.8, 2.8))  # 🔸 Diğer grafiklere daha uyumlu

    values = {k: v for k, v in data_dict.items() if k in selected_categories}
    total = sum(values.values())

    if total == 0:
        values = {"Hiç Satış Yok": 1}
        ax.text(0.5, 0.5, "Satış Yok", ha="center", va="center", fontsize=6)
        ax.axis("off")
    else:
        labels = list(values.keys())  # 🔹 Burayı ekle

        def autopct_func(pct):
            val = int(round(pct * total / 100.0))
            return f"{val} {label_suffix}\n{pct:.1f}%"   # 🔸 önce adet, sonra yüzde

        ax.pie(
            values.values(),
            labels=labels,
            autopct=autopct_func,
            startangle=140,
            textprops={'fontsize': 4},
        )

    ax.set_title(title, fontsize=10, fontweight='bold')

    img = io.BytesIO()
    plt.tight_layout()
    plt.savefig(img, format='png', dpi=200)
    img.seek(0)
    encoded = base64.b64encode(img.getvalue()).decode('utf8')
    plt.close(fig)
    return encoded


@app.route("/filtered_sold_chart", methods=["POST"])
def filtered_chart():
    data_dict = {}
    if 'data' in session:
        df = pd.DataFrame(session['data'])
        categories = ["AdaHome", "AdaPanel", "AdaWall"]
        for cat in categories:
            cat_df = df[df["Malzeme Grubu"].str.contains(cat, case=False, na=False)]
            data_dict[cat] = cat_df["Net Satış Miktarı"].sum()

    selected = request.get_json().get("selected_categories", [])
    total = sum(data_dict.get(k, 0) for k in selected)

    fig, ax = plt.subplots(figsize=(4, 4))
    if total == 0:
        ax.text(0.5, 0.5, "Seçilen kategorilerde satış yok", ha="center", va="center", fontsize=10)
        ax.axis("off")
    else:
        values = {k: data_dict[k] for k in selected}
        labels = [f"{k}: {v:.0f} adet\n({v/total*100:.1f}%)" for k, v in values.items()]
        ax.pie(values.values(), labels=labels, startangle=140, textprops={'fontsize': 10})
        ax.set_title("Satılan Ürünler (Filtrelenmiş)", fontsize=12, fontweight='bold')

    img = io.BytesIO()
    plt.tight_layout()
    plt.savefig(img, format='png', dpi=200)
    img.seek(0)
    encoded = base64.b64encode(img.getvalue()).decode('utf8')
    plt.close(fig)
    return encoded

@app.route("/", methods=["GET", "POST"])
def upload_file():
    recommendations_html = None
    missing_recommendations_html = None
    table_data = None
    missing_products_html = None

    pie_chart_url = None
    pie_chart_url2 = None
    pie_chart_url3 = None

    if request.method == "POST" and 'file' in request.files:
        file = request.files['file']
        if file:
            file_path = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(file_path)
            try:
                df_cleaned = detect_and_extract_columns(file_path)
                session['data'] = df_cleaned.to_dict(orient="records")

                table_data = df_cleaned.to_dict(orient="records")
                recommendations_html = generate_recommendations(df_cleaned)

                satilan_urunler = set(df_cleaned["Malzeme Grubu"].astype(str).str.strip())
                satilmayan_urunler = urun_katalogu - satilan_urunler

                missing_products_html = "<br>".join(sorted(satilmayan_urunler)) if satilmayan_urunler else "✅ Tüm ürünler satılmış!"
                missing_recommendations_html = generate_missing_recommendations(satilmayan_urunler)

                charts = generate_pie_charts(satilan_urunler, satilmayan_urunler, df_cleaned)
                pie_chart_url, pie_chart_url2, pie_chart_url3 = charts

            except Exception as e:
                return f"Hata oluştu:<br><pre>{str(e)}</pre>"

    return render_template("index.html",
                           table_data=table_data,
                           missing_products=missing_products_html,
                           missing_recommendations=missing_recommendations_html,
                           recommendations=recommendations_html,
                           pie_chart_url=pie_chart_url,
                           pie_chart_url2=pie_chart_url2,
                           pie_chart_url3=pie_chart_url3)


@app.route("/admin", methods=["GET", "POST"])
def admin_panel():
    rules = load_rules()
    missing_rules = load_missing_rules()

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

        elif action == "add_missing":
            keyword = request.form.get("missing_keyword").strip()
            message = request.form.get("missing_message")
            missing_rules.append({"keyword": keyword, "message": message})
            save_missing_rules(missing_rules)

        elif action == "delete_missing":
            index = int(request.form.get("missing_index"))
            if 0 <= index < len(missing_rules):
                del missing_rules[index]
                save_missing_rules(missing_rules)

        return redirect(url_for("admin_panel"))

    return render_template("admin.html", rules=rules, missing_rules=missing_rules)


if __name__ == "__main__":
    app.run(debug=True)