# recommendations.py

# Öneri kurallarını buraya tanımlıyoruz
recommendation_rules = [
    {
        "condition": lambda row: "AdaHome Dolgulu Yastık" in row["Malzeme Grubu"] and row["Net Satış Miktarı"] < 10,
        "message": "AdaHome Dolgulu Yastık ürünü az satılıyor. Kampanyalar düzenleyerek satışlarınızı artırabilirsiniz!"
    },
    {
        "condition": lambda row: "Kumaş" in row["Malzeme Grubu"] and row["Net Satış Miktarı"] < 5,
        "message": "Kumaş ürünleriniz düşük satılıyor. Daha fazla müşteri çekmek için fiyat stratejinizi gözden geçirebilirsiniz."
    },
    {
        "condition": lambda row: row["Net Satış Miktarı"] == 0,
        "message": "Bu ürün hiç satılmamış! Ürünü tanıtmak için reklam kampanyaları yapabilirsiniz."
    }
]

def generate_recommendations(df):
    """Belirlenen kurallara göre öneriler üretir."""
    recommendations = []
    for _, row in df.iterrows():
        for rule in recommendation_rules:
            if rule["condition"](row):
                recommendations.append(f"<strong>{row['Malzeme Grubu']}</strong>: {rule['message']}")

    return "<br>".join(recommendations) if recommendations else None
